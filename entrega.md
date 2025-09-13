# ENTREGA CONVOCATORIA JUNIO
Hao Zhou

h.zhou.2021@alumnos.urjc.es

## Parte básica

El programa ha sido probado en Chrome ya que en Firefox no funciona.

EL orden de lanzamiento del programa en la consola es como indica en el enunciado:

- python3 signaling.py <signal_port>
- python3 streamer.py <file> <signal_ip> <signal_port>
- python3 front.py <http_port> <signal_ip> <signal_port>

No se ha encontrado con ningun error a destacar.

## Parte adicional

 * Persistencia: Como se indica en enunciado se utiliza un fichero XML. Si existe el fichero, el programa leerá su
 contenido y lo cargará, pero en caso contrario simplemente creará dicho fichero XML. Cada vez que se realice las 
 conexiones entre el servidor de señalizacion y servidor de streaming se guarda la información de interes en el 
 fichero XML, de esta manera si el servidor de streaming aún no se activa, con solo inicializar el servidor
 de señalización y el front habrá contenido para cargar la pagina web, auqnue no pueda reproducir los videos.
 Esto ocurrirá siempre y cuando el fichero XML tenga informaciones. En general no hay ningun error.


 * Información adicional para los ficheros: Se le entrega al servidor de señalización la información adicional por parte
 del streaming para luego servirlo al front que se observandola en el navegador. Se obtiene esa información a partir de
 una pequeña base de datos pudiendo añadir mas cosas aparte del titulo, podriamos añadir descripciones, foto,etc. En
 caso de que no exista en la base de datos simplemente tomala el nombre del fichero.mp4 como titulo, teniendo en cuenta
 que el nombre del fichero.mp4 no haya espacios o que la separación del nombre sea con "_" por ejemplo Juan_Corre.mp4.

 
## Video demostración
 [link del video ](https://youtu.be/UDdji_xxHKg)
