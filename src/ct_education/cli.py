"""Argparse entry point with aggregate output and sanitized failures."""

import argparse
import json
import logging
import sys
import warnings

from .dicom import Collection
from .pipeline import build
from .safety import PipelineError
from .server import create_server


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise PipelineError("E_ARGUMENTS")


def main(argv=None):
    parser = Parser(prog="ct-edu", description="Local CT education; not for diagnosis.")
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("inspect", help="Inventory headers without printing identifying fields.")
    inspect.add_argument("--input", required=True)
    build_parser = commands.add_parser("build", help="Build a new external workspace; overwrite is not supported.")
    build_parser.add_argument("--input", required=True)
    build_parser.add_argument("--workspace", required=True)
    build_parser.add_argument("--series-number", type=int)
    build_parser.add_argument("--annotations")
    serve = commands.add_parser("serve", help="Serve a completed workspace on loopback only.")
    serve.add_argument("--workspace", required=True)
    serve.add_argument("--port", type=int, default=8787)
    video = commands.add_parser("render-video", help="Render a private MP4 using the local viewer; requires the video extra and ffmpeg.")
    video.add_argument("--workspace", required=True)
    video.add_argument("--output", help="New MP4 within the workspace; defaults to workspace/tour.mp4.")
    video.add_argument("--duration", type=float, default=20)
    video.add_argument("--fps", type=int, default=15)
    video.add_argument("--width", type=int, default=1280)
    video.add_argument("--height", type=int, default=720)
    video.add_argument("--port", type=int, default=0)
    previous_logging = logging.root.manager.disable
    try:
        logging.disable(logging.CRITICAL)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            args = parser.parse_args(argv)
            if args.command == "inspect":
                with Collection(args.input) as collection:
                    print(json.dumps(collection.inventory(), allow_nan=False))
            elif args.command == "build":
                manifest = build(args.input, args.workspace, args.series_number, args.annotations)
                print(json.dumps({"status": "complete", "slice_count": manifest["source"]["slice_count"], "layer_count": len(manifest["layers"])}))
            elif args.command == "render-video":
                from .video import render_video

                result = render_video(args.workspace, args.output, duration=args.duration,
                                      fps=args.fps, width=args.width, height=args.height, port=args.port)
                print(json.dumps(result))
            else:
                if not 1 <= args.port <= 65535:
                    raise PipelineError("E_PORT")
                with create_server(args.workspace, args.port, require_frontend=True) as server:
                    print(f"Local viewer: http://127.0.0.1:{args.port}", flush=True)
                    server.serve_forever()
        return 0
    except KeyboardInterrupt:
        return 130
    except PipelineError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except Exception:
        print("E_OPERATION_FAILED", file=sys.stderr)
        return 2
    finally:
        logging.disable(previous_logging)


if __name__ == "__main__":
    sys.exit(main())
