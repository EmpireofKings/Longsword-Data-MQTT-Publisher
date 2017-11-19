import csv
import json
import struct
from gattlib import GATTRequester
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
import logging
import time
import argparse
import os
import boto3
import math
from pygame import mixer

verbose = False
speech = True
countDown = False
iot = True
csvLog = False

# Custom MQTT message callback
def customCallback(client, userdata, message):
    print("Received a new message: ")
    print(message.payload)
    print("from topic: ")
    print(message.topic)
    print("--------------\n\n")

# Plays text-to speech sound
def playTextToSpeech(ssmlText):
	if os.path.exists('ssmlSpokenText.mp3'):
		os.remove('ssmlSpokenText.mp3') # Delete mp3 disk file buffer if exists
	ssmlSpokenText = polly.synthesize_speech(Text = ssmlText, OutputFormat='mp3', VoiceId = 'Brian', TextType='ssml')
	with open('ssmlSpokenText.mp3', 'wb') as f:
	        f.write(ssmlSpokenText['AudioStream'].read())
        	f.close()
	mixer.init()
	mixer.music.load('ssmlSpokenText.mp3')
	mixer.music.play()
	while mixer.music.get_busy() == True:
        	pass
	mixer.quit()
	os.remove('ssmlSpokenText.mp3')

# Read in command-line parameters
parser = argparse.ArgumentParser()
parser.add_argument("-e", "--endpoint", action="store", required=True, dest="host", help="Your AWS IoT custom endpoint")
parser.add_argument("-r", "--rootCA", action="store", required=True, dest="rootCAPath", help="Root CA file path")
parser.add_argument("-c", "--cert", action="store", dest="certificatePath", help="Certificate file path")
parser.add_argument("-k", "--key", action="store", dest="privateKeyPath", help="Private key file path")
parser.add_argument("-w", "--websocket", action="store_true", dest="useWebsocket", default=False,
                    help="Use MQTT over WebSocket")
parser.add_argument("-id", "--clientId", action="store", dest="clientId", default="basicPubSub",
                    help="Targeted client id")
parser.add_argument("-t", "--topic", action="store", dest="topic", default="sdk/test/Python", help="Targeted topic")

args = parser.parse_args()
host = args.host
rootCAPath = args.rootCAPath
certificatePath = args.certificatePath
privateKeyPath = args.privateKeyPath
useWebsocket = args.useWebsocket
clientId = args.clientId
topic = args.topic

if args.useWebsocket and args.certificatePath and args.privateKeyPath:
    parser.error("X.509 cert authentication and WebSocket are mutual exclusive. Please pick one.")
    exit(2)

if not args.useWebsocket and (not args.certificatePath or not args.privateKeyPath):
    parser.error("Missing credentials for authentication.")
    exit(2)

# Configure logging
logger = logging.getLogger("AWSIoTPythonSDK.core")
logger.setLevel(logging.ERROR)
streamHandler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
streamHandler.setFormatter(formatter)
logger.addHandler(streamHandler)

# Init AWSIoTMQTTClient
myAWSIoTMQTTClient = None
if useWebsocket:
    myAWSIoTMQTTClient = AWSIoTMQTTClient(clientId, useWebsocket=True)
    myAWSIoTMQTTClient.configureEndpoint(host, 443)
    myAWSIoTMQTTClient.configureCredentials(rootCAPath)
else:
    myAWSIoTMQTTClient = AWSIoTMQTTClient(clientId)
    myAWSIoTMQTTClient.configureEndpoint(host, 8883)
    myAWSIoTMQTTClient.configureCredentials(rootCAPath, privateKeyPath, certificatePath)

# AWSIoTMQTTClient connection configuration
myAWSIoTMQTTClient.configureAutoReconnectBackoffTime(1, 32, 20)
myAWSIoTMQTTClient.configureOfflinePublishQueueing(-1)  # Infinite offline Publish queueing
myAWSIoTMQTTClient.configureDrainingFrequency(2)  # Draining: 2 Hz
myAWSIoTMQTTClient.configureConnectDisconnectTimeout(10)  # 10 sec
myAWSIoTMQTTClient.configureMQTTOperationTimeout(5)  # 5 sec


polly = boto3.client('polly') # Polly text-to-speech engine
introSsmlText = "<speak>Welcome to the Historical European Martial Arts training. Together, we will train the German Longsword techniques, created by the 14th-century fencing master, <lang xml:lang=\"de-DE\">Johannes Liechtenauer.</lang> To score your technique, I utilize cloud computing, deep learning, and the real time data generated by your swords' sensors. I will call for a guard or a strike, and you can execute it. So, grab your sword! We start in: 3. 2. 1.</speak>"

if speech == True:
	playTextToSpeech(introSsmlText) # Play Intro speech

# List of SSML speech to be pronounced, with class index
longswordMovements = [""] * 7
longswordMovements[0] =  "<speak>Guards: <lang xml:lang=\"de-DE\">Vom tag.</lang></speak>"
longswordMovements[1] =  "<speak><lang xml:lang=\"de-DE\">Ochs.</lang></speak>"
longswordMovements[2] =  "<speak><lang xml:lang=\"de-DE\">Pflug.</lang></speak>"
longswordMovements[3] =  "<speak><lang xml:lang=\"de-DE\">Wechsel.</lang></speak>"
longswordMovements[4] =  "<speak>Strikes: <lang xml:lang=\"de-DE\">Mittelhaw.</lang></speak>"
longswordMovements[5] =  "<speak><lang xml:lang=\"de-DE\">Oberhaw.</lang></speak>"
longswordMovements[6] =  "<speak><lang xml:lang=\"de-DE\">Zwerhaw.</lang></speak>"

# Connect and subscribe to AWS IoT
myAWSIoTMQTTClient.connect()
if verbose == True and iot == True:
	myAWSIoTMQTTClient.subscribe(topic, 1, customCallback)
print("Accepting BLE data in 2 seconds...")
time.sleep(2)
print("Started!")

# Publish to the same topic in a loop forever
loopCount = 0
publishDelay = 0.015 # seconds
afterSpeechDelay = 0.100 # second
dataPointsPerMovement = 4
dataPointsPerMovementIteration = 4

bufferSize = 1 # 4 packets x 20 bytes per packet MAX (5 x int32)
class ImuPacket(): pass # Stores imu packet: timestamp and payload
class ImuPayload(): pass # Stores imu data

trainingLive = True # While true, loop
while trainingLive == True:
	try:

		req = GATTRequester("98:4f:ee:10:d4:90") # BLE genuino 101 address
		
		for classIndex in range(len(longswordMovements)):
			
			if verbose == True:
				print("Playing ssml: ", longswordMovements[classIndex]);
			if speech == True:
				playTextToSpeech(longswordMovements[classIndex]) # Play movement text-to-speech

			time.sleep(afterSpeechDelay)
	
			for dataPoints in range(dataPointsPerMovement): # get  data points

				if (dataPoints % dataPointsPerMovementIteration == 0 or dataPoints == 0) and classIndex > 3:
					if speech == True and countDown == True:

						playTextToSpeech(str("<speak>Get ready!</speak>"))
						time.sleep(afterSpeechDelay)
						playTextToSpeech(str("<speak>" + str((dataPoints / dataPointsPerMovementIteration) + 1) + "</speak>"))				
				data = [[] for i in range(20)] # Accel
				data2 = [[] for i in range(20)] # Gyro
				data3 = [[] for i in range(20)] # Steps, temp
				data4 = [[] for i in range(20)] # Accel2
				#data5 = [[] for i in range(20)] # Gyro2
				#data6 = [[] for i in range(20)] # Magnetometer

		        	for i in range(bufferSize): # Read IMU data # TODO in between delay
	        		        data[i] = req.read_by_uuid("3a19")[0]
					data2[i] = req.read_by_uuid("3a20")[0]
					#time.sleep(publishDelay)
					data3[i] = req.read_by_uuid("3a21")[0]
					data4[i] = req.read_by_uuid("3a22")[0]
					#data5[i] = req.read_by_uuid("3a23")[0]
					#data6[i] = req.read_by_uuid("3a24")[0]
					#time.sleep(publishDelay)
					#print("data4[i] length: ", len(data4[0]))
				
				
				if (dataPoints % dataPointsPerMovementIteration == 0 or dataPoints == 0) and classIndex > 3:
					if speech == True and countDown == True:
						playTextToSpeech(str("<speak>OK!</speak>"))

				imuPacketList = []
				for j in range(0, bufferSize):

			                currentImuPayload = ImuPayload()
		        	        currentImuPayload.ax = struct.unpack_from('i', data[j], 0)[0]
			                currentImuPayload.ay = struct.unpack_from('i', data[j], 4)[0]
		        	        currentImuPayload.az = struct.unpack_from('i', data[j], 8)[0]

			                currentImuPayload.gx = struct.unpack_from('i', data[j], 12)[0]
			                currentImuPayload.gy = struct.unpack_from('i', data2[j], 0)[0]
	        		        currentImuPayload.gz = struct.unpack_from('i', data2[j], 4)[0]

	                                currentImuPayload.ax2 = struct.unpack_from('i', data2[j], 8)[0]
        	                        currentImuPayload.ay2 = struct.unpack_from('i', data2[j], 12)[0]
                	                currentImuPayload.az2 = struct.unpack_from('i', data3[j], 0)[0]

	                                currentImuPayload.gx2 = struct.unpack_from('i', data3[j], 4)[0]
					currentImuPayload.gy2 = struct.unpack_from('i', data3[j], 8)[0]
					currentImuPayload.gz2 = struct.unpack_from('i', data3[j], 12)[0]

					currentImuPayload.mx = struct.unpack_from('i', data4[j], 0)[0]
					currentImuPayload.my = struct.unpack_from('i', data4[j], 4)[0]
					currentImuPayload.mz = struct.unpack_from('i', data4[j], 8)[0]

					currentImuPayload.steps = struct.unpack_from('i', data4[j], 12)[0]
					#currentImuPayload.temp = struct.unpack_from('i', data4[j], 12)[0]
					currentImuPayload.temp = int(math.sqrt((math.sqrt(currentImuPayload.ax2**2))))

					currentImuPayload.classification = classIndex # Current gesture class #TODO: vui change

					currentImuPacket = ImuPacket()
	                		currentImuPacket.timestamp = round(time.time(), 3)
			                currentImuPacket.data = currentImuPayload
        			        imuPacketList.append(currentImuPacket)

                                        if csvLog == True:
                                                with open('longsword.csv', 'a') as csvfile:
							csvWriter = csv.writer(csvfile, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
							#csvWriter.writerow(['classification','ax','ay','az','gx','gy','gz','ax2','ay2','az2','gx2','gy2','gz2','mx','my','mz','steps','temp'])
							csvWriter.writerow([currentImuPayload.classification, 
							currentImuPayload.ax, currentImuPayload.ay, currentImuPayload.az, \
							currentImuPayload.gx, currentImuPayload.gy, currentImuPayload.gz, \
							currentImuPayload.ax2, currentImuPayload.ay2, currentImuPayload.az2, \
							currentImuPayload.gx2, currentImuPayload.gy2, currentImuPayload.gz2, \
							currentImuPayload.mx, currentImuPayload.my, currentImuPayload.mz, \
							currentImuPayload.steps, currentImuPayload.temp])


				msg = json.dumps(imuPacketList[0], default=lambda o: o.__dict__)
				if verbose == True:
					print msg
				if iot == True:
					myAWSIoTMQTTClient.publish(topic, msg, 1) # Publish to DynamoDB via IoT
				loopCount += 1
				time.sleep(publishDelay)			

	except Exception, e:
		print "Exception. Retrying... " + str(e)
		time.sleep(2)
		#pass

	trainingLive = False

# TODO: get score from stateful RESTful service
# Play outro speech
outroSsmlText = "<speak>Session complete! Your score is: 62%. Now, I can use your data to also become better at grading. Thank you for using longsword training.</speak>"
if speech == True:
	playTextToSpeech(outroSsmlText)

print('Exiting the loop');
myAWSIoTMQTTClient.disconnect()
print('Disconnected from AWS')
