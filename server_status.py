from mcstatus import JavaServer



def check_server():
    server = JavaServer.lookup("24.12.64.159")
    try:
        latency = server.status().latency
        return True
    except:
        return False 
