import socket
import threading

SERVER_IP = "10.30.43.9"  # à changer si serveur sur un autre PC
PORT = 5000


username = input("Choisis ton pseudo : ").strip()

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect((SERVER_IP, PORT))

# On envoie le pseudo au serveur
client.sendall(username.encode("utf-8"))

# Le serveur répond s'il accepte ou pas
response = client.recv(1024).decode("utf-8")

if response.startswith("USERNAME_REFUSED"):
    print("Connexion refusée :", response)
    client.close()
    exit()

elif response == "USERNAME_ACCEPTED":
    print(f"Connecté en tant que {username}")


def receive_messages():
    while True:
        try:
            data = client.recv(1024)

            if not data:
                break

            print("\n" + data.decode("utf-8"))
            print("> ", end="")

        except:
            break


threading.Thread(target=receive_messages, daemon=True).start()

print("Écris un message puis appuie sur Entrée.")

while True:
    message = input("> ")

    if message.lower() == "quit":
        break

    client.sendall(message.encode("utf-8"))

client.close()