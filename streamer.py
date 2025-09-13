import argparse
import asyncio
import math
import json
import cv2
import numpy
import sys
import datetime
from aiortc import (RTCPeerConnection, RTCSessionDescription, VideoStreamTrack)
from aiortc.contrib.media import MediaBlackhole, MediaPlayer
from av import VideoFrame


cliente = ""
offer_recibido = ""
answer_enviado = ""
bye_recibido = ""
remote_addr = ""
informacionFicheros = {}


class FlagVideoStreamTrack(VideoStreamTrack):
    """
    A video track that returns an animated flag.
    """

    def __init__(self):
        super().__init__()  # don't forget this!
        self.counter = 0
        height, width = 480, 640

        # generate flag
        data_bgr = numpy.hstack(
            [
                self._create_rectangle(
                    width=213, height=480, color=(255, 0, 0)
                ),  # blue
                self._create_rectangle(
                    width=214, height=480, color=(255, 255, 255)
                ),  # white
                self._create_rectangle(width=213, height=480, color=(0, 0, 255)),  # red
            ]
        )

        # shrink and center it
        h = numpy.float32([[0.5, 0, width / 4], [0, 0.5, height / 4]])
        data_bgr = cv2.warpAffine(data_bgr, h, (width, height))

        # compute animation
        omega = 2 * math.pi / height
        id_x = numpy.tile(numpy.array(range(width), dtype=numpy.float32), (height, 1))
        id_y = numpy.tile(
            numpy.array(range(height), dtype=numpy.float32), (width, 1)
        ).transpose()

        self.frames = []
        for k in range(30):
            phase = 2 * k * math.pi / 30
            map_x = id_x + 10 * numpy.cos(omega * id_x + phase)
            map_y = id_y + 10 * numpy.sin(omega * id_x + phase)
            self.frames.append(
                VideoFrame.from_ndarray(
                    cv2.remap(data_bgr, map_x, map_y, cv2.INTER_LINEAR), format="bgr24"
                )
            )

    async def recv(self):
        pts, time_base = await self.next_timestamp()

        frame = self.frames[self.counter % 30]
        frame.pts = pts
        frame.time_base = time_base
        self.counter += 1
        return frame

    def _create_rectangle(self, width, height, color):
        data_bgr = numpy.zeros((height, width, 3), numpy.uint8)
        data_bgr[:, :] = color
        return data_bgr


async def run(pc, player, recorder, role, args):
    log_message("Comienzo")

    def add_tracks():
        if player and player.audio:
            pc.addTrack(player.audio)

        if player and player.video:
            pc.addTrack(player.video)
        else:
            pc.addTrack(FlagVideoStreamTrack())

    @pc.on("track")  # Se activa cuando hace la conexion, Solo se hace en el servidor.
    def on_track(track):
        print("Receiving %s" % track.kind)
        recorder.addTrack(track)

    global cliente
    # consume signaling
    if cliente == "":
        loop = asyncio.get_running_loop()

        if args.video_file not in informacionFicheros:
            nombre_sin_extension = args.video_file.split(".")[0]
            nombre_con_espacios = nombre_sin_extension.replace('_', ' ')
            args.video_file = 'video_' + args.video_file
            diccionario_mensaje = {args.video_file: {"Titulo": nombre_con_espacios}}
        else:
            diccionario_mensaje = {args.video_file: informacionFicheros[args.video_file]}

        message = "REGISTER STREAMER-" + json.dumps(diccionario_mensaje)
        on_con_lost = loop.create_future()
        cliente = EchoClientProtocol(message, on_con_lost)
        global remote_addr
        remote_addr = (args.signal_ip, args.signal_port)
        await loop.create_datagram_endpoint(lambda: cliente, remote_addr=remote_addr)

    while True:
        await wait_offer_recibido()
        offer = json.loads(offer_recibido)
        sdp = offer["sdp"]
        obj = RTCSessionDescription(sdp=sdp, type="offer")

        if isinstance(obj, RTCSessionDescription):
            await pc.setRemoteDescription(obj)
            if obj.type == "offer":  # Solo server
                # send answer
                add_tracks()
                await pc.setLocalDescription(await pc.createAnswer())
                global answer_enviado
                answer_enviado = json.dumps(pc.localDescription.__dict__)
                log_message('Mensaje de respuesta SDP al navegador enviado a' + str(remote_addr))
                print("Send: ", answer_enviado)
                cliente.transport.sendto(answer_enviado.encode())

                # Guardar el SDP local en el fichero de texto
                str_sdp = pc.localDescription.sdp  # Saco el str del SDP local
                nombre_sin_extension = args.video_file.split(".")[0]
                with open(f"streamer_data{nombre_sin_extension}.sdp", 'w') as f:
                    f.write(str_sdp)

        log_message('Comienzo conexion WebRTC con el navegador')
        await wait_bye_recibido()


class EchoClientProtocol:
    def __init__(self, message, on_con_lost):
        self.message = message
        self.on_con_lost = on_con_lost
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport
        log_message('Mensaje REGISTRO enviado a ' + str(remote_addr))
        self.transport.sendto(self.message.encode())

    def datagram_received(self, data, addr):
        if data.decode().split('"')[len(data.decode().split('"')) - 2] == "offer":
            # Accept the offer
            log_message('Mensaje de oferta SDP del navegador recibido de ' + str(addr))
            print("Received:", data.decode())
            global offer_recibido
            offer_recibido = data.decode()

    def error_received(self, exc):
        print('Error received:', exc)

    def connection_lost(self):
        print("Connection closed")
        self.on_con_lost.set_result(True)


async def wait_offer_recibido():
    while offer_recibido == "":
        await asyncio.sleep(1)


async def wait_bye_recibido():
    while bye_recibido == "":
        await asyncio.sleep(1)


def log_message(message):
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3]
    log_entry = f"{timestamp} {message}"
    sys.stderr.write(log_entry + "\n")


def reset_variables_globales():
    global offer_recibido
    global answer_enviado
    global bye_recibido
    offer_recibido = ""
    answer_enviado = ""
    bye_recibido = ""


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("video_file", help="Video file to stream")
    parser.add_argument("signal_ip", help="Signaling server IP address")
    parser.add_argument("signal_port", type=int, help="Signaling server port")
    args = parser.parse_args()
    pc = RTCPeerConnection()
    # create media source
    if args.video_file:
        player = MediaPlayer(args.video_file)
    else:
        player = None

    recorder = MediaBlackhole()

    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(
            run(
                pc=pc,
                player=player,
                recorder=recorder,
                role="answer",
                args=args
            )
        )
    except KeyboardInterrupt:
        pass
    finally:
        # cleanup
        loop.run_until_complete(recorder.stop())
        loop.run_until_complete(pc.close())


if __name__ == "__main__":
    main()
