from flask import Flask, send_file, request, send_from_directory
import json
from rover import Driver
import signal
import sys
from rover import MotorController
from subprocess import call

app = Flask(__name__)
roverDriver = None


@app.route("/")
def getPageHTML():
    return send_file("index.html")


@app.route('/js/<path:path>')
def send_js(path):
    return send_from_directory('js', path)


@app.route("/sendCommand", methods=['POST'])
def setCommand():
    commandObj = json.loads(request.data.decode("utf-8"))
    newBearing = commandObj['bearing']
    soft = commandObj['soft']
    newLook = commandObj['look']

    if newBearing in MotorController.validBearings:
        if newBearing == "0":
            roverDriver.stop()
        else:
            roverDriver.setBearing(newBearing, soft)
    else:
        print("Invalid bearing {}".format(newBearing))
        return "Invalid", 400

    if newLook == 0:
        roverDriver.lookStop()
    elif newLook == -1:
        roverDriver.lookUp()
    elif newLook == 1:
        roverDriver.lookDown()
    else:
        print("Invalid look at {}".format(newLook))
        return "Invalid", 400

    return "OK"

@app.route("/shutDown", methods=['POST'])
def shutdown():
    call("sudo halt", shell=True)

def signal_handler(signal, frame):
    roverDriver.cleanup()
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    roverDriver = Driver()
    app.run(host='0.0.0.0', port=5000, debug=False)
