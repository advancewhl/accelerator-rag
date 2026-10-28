"""python -m accelerator_rag.rag --config runtime.json [--query QUESTION]."""

import argparse
import json


def main():
    parser = argparse.ArgumentParser(description="Standalone grounded RAG")
    parser.add_argument("--config", required=True)
    parser.add_argument("--query")
    parser.add_argument("--port", type=int, default=8003)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    if args.query:
        from .runtime import RagRuntime

        with RagRuntime(args.config) as runtime:
            runtime.check_generation_service()
            print(json.dumps(runtime.answer(args.query), ensure_ascii=False, indent=2))
    else:
        import uvicorn
        from .api import create_app

        uvicorn.run(create_app(config_path=args.config), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
