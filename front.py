import argparse
import asyncio
import json
import logging
import os
import platform
import jinja2
import sys
import datetime
from aiohttp import web
from aiortc import RTCSessionDescription
from aiortc.contrib.media import MediaPlayer, MediaRelay
from aiortc.rtcrtpsender import RTCRtpSender

ROOT = os.path.dirname(__file__)

relay = None
webcam = None
lista_recibido = []
answer_recibido = ""
cliente = None
remote_addr = ""
titulos = []


def create_local_tracks(play_from, decode):
    global relay, webcam

    if play_from:
        player = MediaPlayer(play_from, decode=decode)
        return player.audio, player.video
    else:
        options = {"framerate": "30", "video_size": "640x480"}
        if relay is None:
            if platform.system() == "Darwin":
                webcam = MediaPlayer(
                    "default:none", format="avfoundation", options=options
                )
            elif platform.system() == "Windows":
                webcam = MediaPlayer(
                    "video=Integrated Camera", format="dshow", options=options
                )
            else:
                webcam = MediaPlayer("/dev/video0", format="v4l2", options=options)
            relay = MediaRelay()
        return None, relay.subscribe(webcam.video)


def force_codec(pc, sender, forced_codec):
    kind = forced_codec.split("/")[0]
    codecs = RTCRtpSender.getCapabilities(kind).codecs
    transceiver = next(t for t in pc.getTransceivers() if t.sender == sender)
    transceiver.setCodecPreferences(
        [codec for codec in codecs if codec.mimeType == forced_codec]
    )


def log_message(message):
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3]
    log_entry = f"{timestamp} {message}"
    sys.stderr.write(log_entry + "\n")


async def index(request):
    loop = asyncio.get_running_loop()
    on_con_lost = loop.create_future()
    message = "LISTA"
    global cliente
    cliente = EchoClientProtocol(message, on_con_lost)
    await loop.create_datagram_endpoint(lambda: cliente, remote_addr=remote_addr)
    await wait_lista_recibido()
    template = jinja2.Template(open(os.path.join(ROOT, "index.html")).read())
    context = {'videos': lista_recibido, 'titulos': titulos}
    return web.Response(text=template.render(context), content_type='text/html')


async def javascript(request):
    content = open(os.path.join(ROOT, "client.js"), "r").read()
    return web.Response(content_type="application/javascript", text=content)


async def offer(request):
    log_message('Mensaje de oferta SDP del navegador recibido')
    params = await request.json()
    log_message('Mensaje de oferta SDP del navegador enviado a (127.0.0.1, 9999)')
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    # Guardar el SDP del navegador en el fichero de texto
    nombre_sin_extension = params["video"].split(".")[0]
    with open(f"front_data{nombre_sin_extension}.sdp", 'w') as f:
        f.write(params["sdp"])

    video_elegido = "Name:" + params["video"]
    print("Send:", video_elegido)
    cliente.transport.sendto(video_elegido.encode())
    print("Send:", json.dumps(offer.__dict__))
    cliente.transport.sendto(json.dumps(offer.__dict__).encode())
    await wait_answer_recibido()
    global answer_recibido
    answer = json.loads(answer_recibido)
    sdp = answer["sdp"]
    log_message('Mensaje de respuesta SDP al navegador enviado')
    answer_recibido = ""
    return web.Response(
        content_type="application/json",
        text=json.dumps(
            {"sdp": sdp, "type": "answer"}
        ),
    )


pcs = set()


async def on_shutdown():
    # close peer connections
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros)
    pcs.clear()


class EchoClientProtocol:
    def __init__(self, message, on_con_lost):
        self.message = message
        self.on_con_lost = on_con_lost
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport
        log_message('Mensaje de peticion del listado de videos enviado a (127.0.0.1, 9999)')
        self.transport.sendto(self.message.encode())

    def datagram_received(self, data, addr):

        if data.decode().split('"')[len(data.decode().split('"')) - 2] == "answer":
            # Accept the offer
            log_message('Mensaje de respuesta SDP al navegador recibido de ' + str(addr))
            global answer_recibido
            print("Received:", data.decode())
            answer_recibido = data.decode()

        try:
            datos_decodificados = json.loads(data.decode())
            if datos_decodificados and datos_decodificados[0].split('"')[1].split("_")[0] == "video":
                log_message('Mensaje de listado de videos recibido de ' + str(addr))
                global lista_recibido, titulos
                print("Received:", datos_decodificados)
                n = 0
                for video in datos_decodificados:
                    lista_recibido.append(str(json.loads(video).keys()).split("'")[1])
                    titulos.append(json.loads(video)[lista_recibido[n]]["Titulo"])
                    n += 1
        except KeyError:
            pass

    def error_received(self, exc):
        print('Error received:', exc)

    def connection_lost(self):
        print("Connection closed")
        self.on_con_lost.set_result(True)


async def wait_lista_recibido():
    global lista_recibido
    lista_recibido.clear()  # Limpiar la lista existente
    while not lista_recibido:
        await asyncio.sleep(1)


async def wait_answer_recibido():
    while answer_recibido == "":
        await asyncio.sleep(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("http_port", type=int, help="TCP port for HTTP requests")
    parser.add_argument("signal_ip", help="Signaling server IP address")
    parser.add_argument("signal_port", type=int, help="Signaling server port")

    args = parser.parse_args()
    global remote_addr
    remote_addr = (args.signal_ip, args.signal_port)
    logging.basicConfig(level=logging.INFO)
    ssl_context = None
    log_message("Comienzo")
    app = web.Application()
    app.on_shutdown.append(on_shutdown)
    app.router.add_get("/", index)
    app.router.add_get("/client.js", javascript)
    app.router.add_post("/offer", offer)
    web.run_app(app, host="127.0.0.1", port=args.signal_port, ssl_context=ssl_context)


if __name__ == "__main__":
    main()
