"""Training YOLO model.

- Author: Jongkuk Lim
- Contact: limjk@jmarple.ai
"""

import argparse
import os
import pprint

import yaml
from kindle import YOLOModel

from scripts.data_loader.data_loader_utils import create_dataloader
from scripts.train.train_model_builder import TrainModelBuilder
from scripts.train.yolo_trainer import YoloTrainer
from scripts.utils.general import colorstr, get_logger

LOCAL_RANK = int(
    os.getenv("LOCAL_RANK", -1)
)  # https://pytorch.org/docs/stable/elastic/run.html
RANK = int(os.getenv("RANK", -1))
WORLD_SIZE = int(os.getenv("WORLD_SIZE", 1))
LOGGER = get_logger(__name__)


def get_parser() -> argparse.Namespace:
    """Get argument parser.

    Modify this function as your porject needs
    """
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "--model",
        type=str,
        default=os.path.join("res", "configs", "model", "yolov5s.yaml"),
        help=colorstr("Model config") + " file path",
    )
    parser.add_argument(
        "--data",
        type=str,
        default=os.path.join("res", "configs", "data", "coco.yaml"),
        help=colorstr("Dataset config") + " file path",
    )
    parser.add_argument(
        "--cfg",
        type=str,
        default=os.path.join("res", "configs", "cfg", "train_config.yaml"),
        help=colorstr("Training config") + " file path",
    )
    parser.add_argument(
        "--local_rank",
        type=int,
        default=-1,
        help="DDP parameter. " + colorstr("red", "bold", "Do not modify"),
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = get_parser()

    with open(args.data, "r") as f:
        data_cfg = yaml.safe_load(f)

    with open(args.cfg, "r") as f:
        train_cfg = yaml.safe_load(f)

    with open(args.model, "r") as f:
        model_cfg = yaml.safe_load(f)

    cfg_all = {
        "data_cfg": data_cfg,
        "train_cfg": train_cfg,
        "model_cfg": model_cfg,
        "config_paths": {
            "data_cfg": args.data,
            "train_cfg": args.cfg,
            "model_cfg": args.model,
        },
    }

    LOGGER.info(
        "\n"
        + colorstr("red", "bold", f"{'-'*30} Training Configs START {'-'*30}")
        + "\n"
        + pprint.pformat(cfg_all, indent=4)
        + "\n"
        + colorstr("red", "bold", f"{'-'*30} Training Configs END {'-'*30}")
    )

    model = YOLOModel(model_cfg, verbose=True)
    train_builder = TrainModelBuilder(model, train_cfg, "exp")
    train_builder.ddp_init()

    stride_size = int(max(model.stride))  # type: ignore

    train_loader, train_dataset = create_dataloader(
        data_cfg["train_path"], train_cfg, stride_size, prefix="[Train] "
    )

    if RANK in [-1, 0]:
        val_loader, val_dataset = create_dataloader(
            data_cfg["val_path"],
            train_cfg,
            stride_size,
            prefix="[Val] ",
            validation=True,
            pad=0.5,
        )
    else:
        val_loader, val_dataset = None, None

    model, ema, device = train_builder.prepare(
        train_dataset, train_loader, nc=len(data_cfg["names"])
    )

    trainer = YoloTrainer(
        model,
        train_cfg,
        train_dataloader=train_loader,
        val_dataloader=val_loader,
        ema=ema,
        device=device,
    )
    trainer.train()
