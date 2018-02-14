import time
from threading import Thread, Condition


import RPi.GPIO as GPIO


class Motor:
    PWM_FREQUENCY = 100

    def __init__(self, isLeft, pwmPin, forwardPin, reversePin, maxDC, minDC, rampUpTime):
        self.isLeft = isLeft
        self.pwmPin = pwmPin
        self.forwardPin = forwardPin
        self.reversePin = reversePin
        self.maxDC = maxDC
        self.minDC = minDC
        self.targetBearing = -1
        self.targetSetTime = -1
        self.rampUpTime = rampUpTime
        self.pwmControl = None
        self.drivingThread = None
        self.drivingThreadSync = Condition()
        self.__initMotor()

    def __initMotor(self):
        GPIO.setup(self.pwmPin, GPIO.OUT)
        GPIO.setup(self.forwardPin, GPIO.OUT)
        GPIO.setup(self.reversePin, GPIO.OUT)
        self.pwmControl = GPIO.PWM(self.pwmPin, self.PWM_FREQUENCY)
        self.pwmControl.start(self.maxDC)
        self.__clear()
        self.startDrivingThread()

    def __clear(self):
        GPIO.output(self.forwardPin, 0)
        GPIO.output(self.reversePin, 0)

    def setBearing(self, bearing):
        with self.drivingThreadSync:
            self.targetBearing = bearing
            self.targetSetTime = time.time()
            self.drivingThreadSync.notify()

    def startDrivingThread(self):
        self.drivingThread = Thread(target=self.doDrive, daemon=True)
        self.drivingThread.start()

    def doDrive(self):
        currentDC = 0
        originalDC = 0
        sleepInterval = 0.1

        while True:
            with self.drivingThreadSync:
                targetDC = self.getTargetDC()

                if targetDC == currentDC:
                    # print("Going on standby")
                    self.drivingThreadSync.wait()
                    # print("Woke up")
                    originalDC = currentDC
                    targetDC = self.getTargetDC()

                targetSetTime = self.targetSetTime

            deltaTime = time.time() - targetSetTime
            timeFraction = min(deltaTime / self.rampUpTime, 1)

            totalDCDelta = targetDC - originalDC
            dcDeltaFraction = totalDCDelta * timeFraction

            previousDC = currentDC
            currentDC = currentDC + dcDeltaFraction

            if (previousDC < 0 and currentDC > 0) or (previousDC > 0 and currentDC < 0):
                currentDC = 0

            # clamp the speed around the target so we don't overshoot
            if originalDC < targetDC:
                # going up
                currentDC = min(currentDC, targetDC)
            else:
                # going down
                currentDC = max(currentDC, targetDC)

            # print("Current DC: {}".format(currentDC))

            if currentDC == 0:
                self.__clear()
            else:
                self.pwmControl.ChangeDutyCycle(int(abs(currentDC)))
                if currentDC < 0:
                    GPIO.output(self.reversePin, 1)
                else:
                    GPIO.output(self.forwardPin, 1)

            time.sleep(sleepInterval)

    def getTargetDC(self):
        currentBearing = self.targetBearing

        if currentBearing == -1:
            rpmFactor = 0
        elif currentBearing <= 90:
            if self.isLeft:
                rpmFactor = 1
            else:
                rpmFactor = float(currentBearing) / 90
        elif currentBearing <= 180:
            if self.isLeft:
                rpmFactor = float(180 - currentBearing) / 90
            else:
                rpmFactor = 1
        elif currentBearing <= 270:
            if self.isLeft:
                rpmFactor = float(currentBearing - 180) / 90
            else:
                rpmFactor = 1
        else:
            if self.isLeft:
                rpmFactor = 1
            else:
                rpmFactor = float(360 - currentBearing) / 90

        understeer = 0.8

        if rpmFactor < 1:
            rpmFactor = rpmFactor * understeer

        targetDC = self.maxDC * rpmFactor

        if targetDC < self.minDC:
            targetDC = 0

        reversing = currentBearing > 180
        if reversing:
            targetDC = targetDC * -1

        return targetDC

class Driver:
    maxDC = 100
    minDC = 0
    rampUpTime = 0.5

    def __init__(self):
        GPIO.setmode(GPIO.BOARD)
        print("Creating motors...")
        self.motor1 = Motor(True, 16, 18, 22, self.maxDC, self.minDC, self.rampUpTime)
        self.motor2 = Motor(False, 15, 13, 11, self.maxDC, self.minDC, self.rampUpTime)

    def setBearing(self, bearing):
        if bearing < 0 or bearing > 359:
            raise ValueError("Invalid bearing: " + bearing)

        self.motor1.setBearing(bearing)
        self.motor2.setBearing(bearing)

    def stop(self):
        self.motor1.setBearing(-1)
        self.motor2.setBearing(-1)

    def cleanup(self):
        GPIO.cleanup()

