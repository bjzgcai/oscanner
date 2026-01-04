from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from dashscope.audio.asr import Recognition, RecognitionCallback, RecognitionResult
import asyncio
import json
from typing import cast

import dashscope
# TODO: move api key to config
dashscope.api_key = "sk-c4063b5a8e094b1691875f05b700a036"

SAMPLE_RATE = 16000
MODEL_NAME = "paraformer-realtime-v2"

app = FastAPI()

async def init_speech_recognition(websocket: WebSocket):
    callback = Callback(websocket)
    recognition = Recognition(
        model=MODEL_NAME,
        format="pcm",
        sample_rate=SAMPLE_RATE,
        callback=callback,
    )
    recognition.start()
    print("Recognition started (model=%s, sample_rate=%d)" % (MODEL_NAME, SAMPLE_RATE))
    try:
        while True:
            try:
                data = await websocket.receive_bytes()
                recognition.send_audio_frame(data)
            except Exception as e:
                print("Error during speech streaming: ", e)
                break
    except WebSocketDisconnect:
        recognition.stop()
    except Exception as e:
        print("WebSocket handler error:", e)

class Callback(RecognitionCallback):
    def __init__(self, websocket: WebSocket) -> None:
        self.websocket = websocket

    def on_event(self, result: RecognitionResult) -> None:
        """
        Called by the recognition library when there's an update.
        Compute incremental new_word and schedule broadcast to connected clients.

        Example response from model:
        {
            'sentence_id': 1,
            'begin_time': 0,
            'end_time': None,
            'text': '你好世界',
            'channel_id': 0,
            'speaker_id': None,
            'sentence_end': False,
            'words': [
                {'begin_time': 0, 'end_time': 940, 'text': '你好', 'punctuation': '', 'fixed': False, 'speaker_id': None},
                {'begin_time': 940, 'end_time': 1880, 'text': '世界', 'punctuation': '', 'fixed': False, 'speaker_id': None},
            ]
        }
        """
        sentence = result.get_sentence()
        sentence = cast(dict, sentence)

        sentence_id = sentence.get("sentence_id") or -1
        text = sentence.get("text")
        res = json.dumps({"id": sentence_id, "sentence": text})

        async def send_text():
            await self.websocket.send_text(res)
        asyncio.run(send_text())
