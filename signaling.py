import asyncio
import json
import argparse
import xml.etree.ElementTree as ET
import os
import sys
import datetime

clientlist = []
streamers = {}
ficheros = []
mensaje_no_enviado = []
streamer_elegido = ""

DIRECTORIO_FILE = "directorio.xml"


def leer_directorio():
    if not os.path.exists(DIRECTORIO_FILE):
        print("Archivo de directorio XML no encontrado. Creando uno nuevo.")
        return {"clientlist": [], "streamers": {}, "ficheros": []}

    tree = ET.parse(DIRECTORIO_FILE)
    root = tree.getroot()

    directorio = {"clientlist": [], "streamers": {}, "ficheros": []}

    for cliente in root.find('ClientList').findall('Cliente'):
        nombre = cliente.find('Nombre').text
        direccion = cliente.find('Direccion').text
        cliente_info = {"Nombre": nombre, "Direccion": eval(direccion)}
        if cliente_info not in directorio["clientlist"]:
            directorio["clientlist"].append(cliente_info)

    for streamer in root.find('Streamers').findall('Streamer'):
        nombre = streamer.find('Nombre').text
        direccion = streamer.find('Direccion').text
        if nombre not in directorio["streamers"]:
            directorio["streamers"][nombre] = eval(direccion)

    for fichero in root.find('Ficheros').findall('Fichero'):
        fichero_text = fichero.text
        if fichero_text not in directorio["ficheros"]:
            directorio["ficheros"].append(fichero_text)

    return directorio


def guardar_directorio(directorio):
    root = ET.Element("Directorio")

    clientlist_element = ET.SubElement(root, "ClientList")
    for cliente in directorio["clientlist"]:
        cliente_element = ET.SubElement(clientlist_element, "Cliente")
        nombre_element = ET.SubElement(cliente_element, "Nombre")
        nombre_element.text = str(cliente["Nombre"])
        direccion_element = ET.SubElement(cliente_element, "Direccion")
        direccion_element.text = str(cliente["Direccion"])

    streamers_element = ET.SubElement(root, "Streamers")
    for nombre, direccion in directorio["streamers"].items():
        streamer_element = ET.SubElement(streamers_element, "Streamer")
        nombre_element = ET.SubElement(streamer_element, "Nombre")
        nombre_element.text = nombre
        direccion_element = ET.SubElement(streamer_element, "Direccion")
        direccion_element.text = str(direccion)

    ficheros_element = ET.SubElement(root, "Ficheros")
    for fichero in directorio["ficheros"]:
        fichero_element = ET.SubElement(ficheros_element, "Fichero")
        fichero_element.text = fichero

    tree = ET.ElementTree(root)
    tree.write(DIRECTORIO_FILE, encoding='utf-8', xml_declaration=True)


def log_message(message):
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3]
    log_entry = f"{timestamp} {message}"
    sys.stderr.write(log_entry + "\n")


class EchoServerProtocol:

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        global clientlist, streamers, ficheros, mensaje_no_enviado, streamer_elegido

        message = data.decode()
        print('Received %r from %s' % (message, addr))

        if message.split("-")[0] == "REGISTER STREAMER":
            for streamer in json.loads(message.split("-")[1]).keys():
                streamers[streamer] = addr
            print(streamers)
            fichero = message.split("-")[1]
            if fichero not in ficheros:
                ficheros.append(fichero)
            log_message("Mensaje REGISTRO STREAMER recibido de " + str(addr))
            guardar_directorio({"clientlist": clientlist, "streamers": streamers, "ficheros": ficheros})

        if message == "LISTA":
            cliente_info = {"Nombre": len(clientlist) + 1, "Direccion": addr}
            if cliente_info not in clientlist:
                clientlist.append(cliente_info)
            print('Send %r to %s' % (ficheros, addr))
            self.transport.sendto(json.dumps(ficheros).encode(), addr)
            guardar_directorio({"clientlist": clientlist, "streamers": streamers, "ficheros": ficheros})

        if message.split(":")[0] == "Name":
            streamer_elegido = message.split(":")[1]

        if len(message.split('"')) >= 2 and message.split('"')[-2] == "offer":
            log_message("Mensaje de oferta SDP recibido de" + str(addr))
            try:
                self.transport.sendto(message.encode(), streamers[streamer_elegido])
                log_message("Mensaje de oferta SDP enviado a " + str(streamers[streamer_elegido]))
            except IndexError:
                print('Send: %r to %s' % ("No hay servidores disponibles", clientlist[-1]["Direccion"]))
                self.transport.sendto(
                    "No hay servidores disponibles, se enviara el mensaje cuando se abra un servidor".encode(),
                    clientlist[-1]["Direccion"])
                mensaje_no_enviado.append(message)

        if len(message.split('"')) >= 2 and message.split('"')[-2] == "answer":
            log_message("Mensaje de respuesta SDP recibido de " + str(addr))
            print('Send %r to %s' % (message, clientlist[-1]["Direccion"]))
            self.transport.sendto(message.encode(), clientlist[-1]["Direccion"])
            log_message("Mensaje de respuesta SDP enviada a" + str(clientlist[-1]["Direccion"]))


async def main():
    global clientlist, streamers, ficheros

    parser = argparse.ArgumentParser()
    parser.add_argument("signal_port", type=int, help="UDP port to listen for signaling messages")
    args = parser.parse_args()
    port = args.signal_port

    log_message("Comienzo")

    directorio = leer_directorio()
    clientlist = directorio["clientlist"]
    streamers = directorio["streamers"]
    ficheros = directorio["ficheros"]

    loop = asyncio.get_running_loop()
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: EchoServerProtocol(),
        local_addr=('127.0.0.1', port))

    try:
        await asyncio.sleep(3600)  # Serve for 1 hour.
    finally:
        directorio = {"clientlist": clientlist, "streamers": streamers, "ficheros": ficheros}
        guardar_directorio(directorio)
        transport.close()


if __name__ == "__main__":
    asyncio.run(main())
