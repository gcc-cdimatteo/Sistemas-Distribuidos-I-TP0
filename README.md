# Parte 1 - Ejercicios Iniciales

## Ejecución Ejercicio N° 1: 
```
./generar-compose.sh docker-compose-dev.yaml [N]
make-docker-compose down
make-docker-compose up
make-docker-compose logs
```
Resultado esperado:
    - 1 echo server
    - `N` clientes conectados
    - `N` clientes enviando la cantidad de mensajes configurada en `client/config.yaml > loop > amount` en loop
    - servidor contestando a cada mensaje el mismo contenido

## Ejecución Ejercicio N° 2:
```
make-docker-compose down
make-docker-compose up
make-docker-compose logs

>>> modificar los archivos client/config.yaml y server/config.ini

make-docker-compose up
make-docker-compose logs
```
Resultado esperado:
    - servidor contestando la nueva cantidad de mensajes configurada en los archivos físicos, sin necesidad de construir nuevamente los containers

## Ejecución Ejercicio N° 3:
```
make-docker-compose down
make-docker-compose up
validar-echo-server.sh
```
Resultado esperado:
    - visualizar por terminal el mensaje `Testing Message From SH`

## Ejecución Ejercicio N° 4:
```
./generar-compose.sh docker-compose-dev.yaml 5
make-docker-compose down
make-docker-compose up
make-docker-compose logs

>>> en otra terminal:

docker kill -s SIGTERM server
```
Resultado esperado:
    - el server y todos los clientes debajo cierran sus tareas correctamente

```
./generar-compose.sh docker-compose-dev.yaml 5
make-docker-compose down
make-docker-compose up
make-docker-compose logs

>>> en otra terminal:

docker kill -s SIGTERM client1
```
Resultado esperado:
    - el container asociado al cliente 1 finaliza, el server sigue levantado escuchando por el resto de las conexiones abiertas

También puede verificarse que la siguiente variación de conexiones finaliza sus tareas de forma correcta:
```
./generar-compose.sh docker-compose-dev.yaml 5
make-docker-compose down
make-docker-compose up
make-docker-compose logs

>>> en otra terminal:

docker kill -s SIGTERM client3
docker kill -s SIGTERM server
```
```
./generar-compose.sh docker-compose-dev.yaml 5
make-docker-compose down
make-docker-compose up
make-docker-compose logs

>>> en otra terminal:

docker kill -s SIGTERM client1
docker kill -s SIGTERM client2
docker kill -s SIGTERM client3
docker kill -s SIGTERM client4
docker kill -s SIGTERM client5
docker kill -s SIGTERM server
```

# Parte 2 - Protocolo de Comunicación
Para la resolución del proyecto en cuestión se tomó la decisión de implementar un protocolo de parquetes de **ancho variable** con el objeto de evitar *short reads* y/o *short writes* durante la comunicación *server - client*. Adicionalmente, con la intención de alcanzar un óptimo en el protocolo, los paquetes son enviados y recibidos en formato **binario**, BigEndian.

Puesto que a partir del Ejercicio N° 8 el presente trabajo implementa concurrencia y -en particular- paralelismo entre procesos, mientras que de los Ejercicios N° 1 a 7 el Servidor corre en un único thread, es de esperarse que el protocolo tenga un cambio de enfoque hacia la finalización del proyecto.

Por esta razón, encontrarán a continuación la explicación del protocolo desarrollado para los Ejercicios N° 1 a 7, y podrán ver en otro subtítulo el desarrollo del protocolo desarrollado para el Ejercicio N° 8 con sus respectivas diferencias de enfoque.

### Server Single Process
Una vez cargadas en memoria las apuestas que cada uno de los Clientes debe enviar al Server, el Cliente abre un Socket que se comunica con la dirección IP y se conecta al puerto por el cual el Server va a estar escuchando por nuevas conexiones. Al recibir una nueva conexión, el Server guarda en una lista de Clientes el nuevo Cliente que se ha generado en el sistema. para representar un Cliente, se creo la clase `Client` dentro del módulo del servidor que alberga toda la información de relevancia del mismo así como demás funcionalidades útiles que hacen al desarrollo del proyecto.

Una vez establecida dicha comunicación (protocolo TCP) el Cliente envía el primero de los mensajes que corresponde -en cualquier escenario- a la carga de una o varias apuestas. Cabe destacar que en el caso del Ejercicio N° 5, se toma el registro de una única apuesta por Cliente recaudando la información necesaria de las variables de entorno. Ahora bien, para los Ejercicios N° 6 y 7 dicha información es obtenida de los archivos descomprimidos de la carpeta ./data. Es importante remarcar que con el objeto de que cada Cliente pueda acceder a los archivos de las apuestas de la carpeta en cuestión, y teniendo en cuenta que cada Cliente está siendo ejecutado en un container aislado de Docker, el Dockerfile de la construcción de los containers de los Clientes contemplan la inyección de dichos datos:
```
COPY ./.data/dataset /dataset
```

Cada mensaje que recibe el Server por parte de un Cliente se crea una nueva instancia de la clase `Message`, que tiene como objeto parsear un string según el formato de interés, así como demás funcionalidades útiles que hacen al desarrollo del trabajo.

Una vez parseado, según la tipificación establecida, el mensaje recibido puede ser:
- `BET`: indica que el mensaje contiene apuestas que el servidor debe almacenar
- `END`: indica que el cliente finalizó con el envío de apuestas, por lo cual el servidor no debe almacenar más apuestas relacionadas a esa agencia
- `WIN`: indica el deseo de un cliente por obtener los ganadores del sorteo
- `CON`: indica que el cliente necesita saber cuáles son los ganadores del sorteo

Cada mensaje (sin excepción) es antecedido por 4 bytes que contienen la información del largo del mensaje restante. En esta línea, el protocolo se ajusta al largo del mensaje que se quiera mandar, y no presenta restricciones en términos de hacer lecturas o escritruas cortas por el canal de comunicación. Sin embargo, y como bien presenta el enunciado de este proyecto, tiene un máximo de 8kB de envío de bytes, con lo cual, cualquier mensaje que se exceda de ese tamaño va a ser particionado y enviado en paquetes más pequeños, con el objeto de no sobrecargar el canal de comunicación. Todo el largo del mensaje es enviado en formato binario, con lo cual es desencodeado durante la recepción al formato según corresponda. Es decir, la lectura de los primeros 4 bytes es desencodeada al tipo entero (BigEndian). La lectura del resto de los bytes (que resulta de desencodear los primeros 4 y convertirlos a entero) es desencodeada al tipo string (en particular, utf-8, también BigEndian).

La razón por la cual se decidió utilizar un entero de 4 bytes para especificar la longitud de un mensaje se debe a que en 32 bits se podrían especificar tamaños de hasta 4 GB (2^32-1 bytes). Si bien el protocolo actualmente sólo permite enviar paquetes de hasta 8kB, se tomó la decisión de dejarlo extensible para futuros proyectos donde se decida extender la longitud de mensajes enviados.

Por último es importante destacar que cada vez que el Cliente envía un mensaje al Servidor, crea una nueva conexión con el Server. Una vez recibe la respuesta de éste, se desconecta para iniciar una nueva conexión a partir del próximo mensaje que tenga que enviar. Cabe aclarar que esto incrementa una conexión equilibrada entre Clientes, de forma tal que cada uno -enviando mensajes pequeños- puede interactuar con el Servidor sin consumirlo por completo.

#### Formato de Mensajes
##### `BET`
Los primeros 4 bytes indican el largo del mensaje. 

La cadena de texto restante es spliteada primero por `\n` (separa los registros de apuestas) y luego por `|` (separa los valores correspondientes a una apuesta). En secuencia, cada uno de los valores obtenidos por la separación por el caracter `|` corresponden a:

- id_agencia
- nombre_apostador
- apellido_apostador
- documento_apostador
- fecha_nacimiento_apostador
- numero_apostado

Ejemplo de cómo se recibirán los mensajes de tipo `BET`:

```
3|Benjamin Alejandro|Varela|20128952|1994-05-23|6123
3|Matias Ariel|Leal|35707621|1982-10-11|3316
3|Brisa Aylen|Silva|31136024|1980-09-24|4138
3|Santiago Alejandro|Arredondo|38648320|1985-01-21|4039
...
```

Una vez finalizada la lectura de dicho mensaje, el servidor responderá con `ACK` si las apuestas se procesaron con éxito, o con un resumen de la cantidad de apuestas rechazadas como `REJECTED [CANTIDAD_APUESTAS_RECHAZADAS]`. Si el cliente recibe un rechazo en el envío de un Batch de apuestas, no detendrá su ejecución: seguirá mandando todas las apuestas que cargó en memoria previamente.

Una vez recibido el mensaje de respuesta por parte del Servidor, el Cliente se desconecta.

##### `END`
Los primeros 4 bytes indican el largo del mensaje. 

La cadena de texto restante es spliteada por `\n`, obteniendo un único elemento de detalle del mensaje.

El servidor responderá con un `END ACK` para indicar que la finalización del envío fue recibida con éxito.

Una vez recibido el mensaje de respuesta por parte del Servidor, el Cliente se desconecta.

##### `WIN`
Los primeros 4 bytes indican el largo del mensaje. 

La cadena de texto restante es spliteada por `\n`, obteniendo un único elemento de detalle del mensaje.

Este mensaje será enviado por cada uno de los Clientes una vez obntengan el `END ACK`, indicando su deseo por querer saber quiénes fueron los ganadores del sorteo.

Por otro lado, el servidor tendrá la responsabilidad de procesar si puede responder a dicha consulta de ganadores, o no. En esta línea, el servidor debe evaluar si recibió los `ENDs` de todos los Clientes que tiene conectados hasta el momento (el largo es variable, no está hardcodeada la cantidad de Clientes logueados en el server) o no.

En el caso de que el Servidor cuente con la totalidad de `ACKs` que necesita para responder la consulta de ganadores, responderá al Cliente con `Y`. Caso contrario, responderá con `N`. Para el envío y lectura de estos mensajes, de igual forma se envían los primeros 4 bytes con el largo del mensaje, y luego la cadena de bytes según corresponda. Vale la pena destacar que el envío y recepción de mensajes se realiza de forma centralizada en las funciones `client.send(msg)` y `client.recv()` del módulo del Server para enviar y recibir mensajes del Cliente, y en las funciones `Send` y `Recv` del módulo del cliente para enviar y recibir mensajes del Servidor.

Mientras que un Cliente siga recibiendo `N` como respuesta a este mensaje, seguirá consultando al Servidor por los ganadores del sorteo. Ahora bien, en pos de no sobrecargar al Servidor de peticiones que se saben probablemente serán negativas, el Cliente espera un cierto tiempo antes de reenviar el mensaje `WIN`. En esta línea, se espera que el próximo envío efectivamete se obtnga `Y` y así minimizar al máximo la cantidad de mensajes que se envían al servidor.

Una vez recibido el mensaje de respuesta por parte del Servidor, el Cliente se desconecta.

##### `CON`
Los primeros 4 bytes indican el largo del mensaje. 

Este mensaje será enviado por cada uno de los Clientes una vez obtengan `Y` como respuesta al mensaje `WIN`, indicando que efectivamente se pueden consultar quiénes fueron los ganadores del sorteo.

La cadena de texto recibida es spliteada primero por `\n` (separa los registros) y luego por `|` (separa los valores correspondientes al número de documento de cada ganador).

Ejemplo de ganadores recibidos para la agencia N° 2: 

```30876370|24807259\n```

Lo que implica que dicha agencia tuvo dos ganadores cuyos números de documento son 30876370 y 24807259.

Una vez recibido el mensaje de respuesta por parte del Servidor, el Cliente se desconecta. Cabe destacar que, en este punto, el proceso del Cliente finaliza y nunca más interactúa con el Servidor.

### Server Multi Process
En pos de incorporar el paralelismo, la concurrencia y la utilización de más de un proceso para completar este punto, ante la apertura de una nueva conexión, el Servidor crea un proceso que representa la conexión de un Cliente. En esta línea, la primer diferencia con la sección previa radica en que la conexión del Cliente al Servidor ya no tiene la necesidad de establecerse cada vez se envía un mensaje, si no que el Cliente crea el socket por el cual se va a conectar con el Servidor, y dicha conexión vive hasta tanto el Cliente no se desconecte luego de obtener los ganadores del sorteo.

Se detallan a continuación los mensajes que sobreviven de la sección anterior.

##### `BET`
Ni el formato ni las respuestas al mensaje cambian respecto de la sección anterior.

Una vez recibido el mensaje de respuesta por parte del Servidor, el Cliente NO se desconecta.

##### `END`
Ni el formato ni las respuestas al mensaje cambian respecto de la sección anterior.

Los cambios realizados en este mensaje corresponden a la lógica del mismo, puesto que el Server utiliza una barrera que le indica que todos los Clientes finalizaron el envío de apuestas. Una vez dicha barrera se levanta, el Servidor procesa las apuestas persistidas y las sube a memoria para que los procesos correspondientes a los Clientes puedan acceder a ellas.

Una vez recibido el mensaje de respuesta por parte del Servidor, el Cliente NO se desconecta.

##### `WIN`
Puesto que no es necesario que el cliente pregunte una y otra vez por el estado de los ganadores (si están disponibles o no), este mensaje queda eliminado.

##### `CON`
Ni el formato ni las respuestas al mensaje cambian respecto de la sección anterior.

Los cambios realizados en este mensaje corresponden a la lógica del mismo, puesto que el Server utiliza una barrera que le indica que todos los Clientes finalizaron el envío de apuestas. Una vez dicha barrera se levanta, el Servidor procesa las apuestas persistidas y las sube a memoria para que los procesos correspondientes a los Clientes puedan acceder a ellas.

Una vez recibido el mensaje de respuesta por parte del Servidor, el Cliente se desconecta finalmente.

# Parte 3 - Mecanismos de Sincronización
Para la implementación de concurrencia y paralelismo en el proyecto se utilizó la librería `multiprocessing` de Python. 

En línea con las restricciones que presenta el GIL en Python, y puesto que cada thread que se spawnee no puede ejecutarse en forma paralela, se tomó la decisión de utilizar un Proceso por cada Cliente que se conecta al Servidor. 

Como cada Proceso tiene un espacio reservado en memoria que no comparte con sus iguales (el resto de los Clientes en la red) se utilizó el `Manager` de la librería para el manejo de recursos compartidos:
- una lista de clientes conectados al servidor (`self.clients_connected`) que permite cerrar las conexiones de los clientes llegado el caso que se lance la señal SIGTERM al Servidor
- una lista de apuestas (`self.bets`) que permite almacenar en memoria la información persistida que resulta de recolectar la información de apuestas de todas las agencias que se conectan al Servidor

Se utilizaron `Locks` para ordenar el acceso a dichos recursos compartidos:
- `self.clients_connected_lock`: se utiliza en conjunto con el listado de clientes conectados
- `self.bets_lock`: se utiliza en conjunto con el listado de apuestas
- `self.bets_file_lock`: si bien se utiliza para lockear el archivo de apuestas, se implementó este lock únicamente como una buena práctica de programación pues dadas las circunstancias de cómo está construido el código, realmente no podría darse el caso que más de dos Procesos quisiesen acceder a dicho recurso -ni al mismo tiempo, ni nunca-

Por último, y de la mano con el último punto descripto, se implementó una `Barrier` para sincronizar no sólo la carga en memoria de la información del archivo de apuestas, si no que avisa a los procesos cuándo efectivamente finalizó el juego y los ganadores se encuentran disponibles para su consulta. En este sentido, el último Proceso que avisa al Cliente que finalizó la carga de apuestas, es el que se encarga de cargar en memoria la persistencia en disco de apuestas (motivo por el cual no sería necesario el lock del archivo) y levantar la barrera para que el resto de los Procesos puedan realizar sus consultas correspondientemente.