"""Initialize bundled local models without settings/credentials or provider clients."""

from livekit.local_inference import init_eot
from livekit.plugins import silero


def prepare():
    # Both models are in locked wheels. Never use the SDK's all-plugin download-files path.
    silero.VAD.load(force_cpu=True)
    init_eot()
    print("Bundled Silero and local mini initialization passed; no provider clients created.")


if __name__ == "__main__":
    prepare()
