import sys
import os

def load_env_file(file_path):
    env_vars = {}
    try:
        with open(file_path, 'r') as f:
            for line in f:
                key, value = line.strip().split('=', 1)
                env_vars[key] = value
    except FileNotFoundError:
        raise Exception(f"Env file {file_path} not found")
    return env_vars

def main():
    args = sys.argv[1:]

    if (len(args) != 2): raise Exception("Must receive filename and amount of clients to be created")

    amount_clients = 0

    try:
        amount_clients = int(args[1])
    except:
        raise TypeError("The amount of clients to be creted must be integer")

    string_builder = ""

    string_builder += """
name: tp0
services:
  server:
    container_name: server
    image: server:latest
    entrypoint: python3 /main.py
    volumes:
      - ./server/config.ini:/config.ini
    environment:
      - PYTHONUNBUFFERED=1
      - LOGGING_LEVEL=DEBUG
    networks:
      - testing_net
    """
    
    for i in range(amount_clients):
      env_vars = load_env_file(f'client{i+1}.env')
      string_builder += f"""
  client{i+1}:
    container_name: client{i+1}
    image: client:latest
    entrypoint: /client
    volumes:
      - ./client/config.yaml:/config.yaml
    environment:
      - CLI_ID={i+1}
      - CLI_LOG_LEVEL=DEBUG
      - NOMBRE={env_vars['NOMBRE']}
      - APELLIDO={env_vars['APELLIDO']}
      - DOCUMENTO={env_vars['DOCUMENTO']}
      - NACIMIENTO={env_vars['NACIMIENTO']}
      - NUMERO={env_vars['NUMERO']}
    networks:
      - testing_net
    depends_on:
      - server
        """
    
    string_builder += """
networks:
  testing_net:
    ipam:
      driver: default
      config:
        - subnet: 172.25.125.0/24
    """

    file = open(args[0], "w")
    file.write(string_builder)
    file.close()

    print(f"{args[0]} created successfully")

main()