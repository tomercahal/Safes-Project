import pyaudio
import wave
import numpy as np
import serial
import pygame
import alsaaudio
from subprocess import call


def play_sound_file(file_name):
    m = alsaaudio.Mixer("PCM")
    m.setvolume(100)
    pygame.mixer.init()
    pygame.mixer.music.load("/home/pi/Safes/" + file_name)  # Need to change according to file location!!
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        continue
    pygame.mixer.quit()
    m.setvolume(0)


def pick_sound_file(lang, start_or_end):
    if lang == "English":
        if start_or_end == "start":
            play_sound_file("startMessageEnglish.mp3")
            return
        play_sound_file("endMessageEnglish.mp3")  # If its not the start then it must be the end
        return
    if start_or_end == "start":  # It must be Hebrew no need to check
        play_sound_file("startMessageHebrew.mp3")
        return
    play_sound_file("endMessageHebrew.mp3")


def start_arduino_connection():
    ser = serial.Serial("/dev/ttyACM0", 9600)
    ser.baudrate = 9600
    return ser


def choose_language_version():
    """This function is called in the start and asks the user which language he wants the safe to be played in"""
    version = raw_input("Hello and welcome to our safe!! Please help Bruce! For the English version please press e,"
                        " for the hebrew version press h\r\nType here: ")
    while True:
        if version == 'e':
            print "English version set up"
            return "English"
        elif version == 'h':
            print "Hebrew version set up"
            return "Hebrew"
        else:
            version = "Wrong input please press e (for English) or h (for Hebrew)\r\nType here: "
            continue


def check_door_status_and_first_riddle(ser):
    arduino_response = ser.readline()[:-2]
    print "The arduino sent: " + arduino_response
    parts_of_response = arduino_response.split(" ")
    print parts_of_response
    if len(parts_of_response) != 2:
        return False
    door_status = parts_of_response[0] == "close"
    first_riddle_status = parts_of_response[1] == "solved"
    if door_status and first_riddle_status:
        return True
    return False

def record():
    CHUNK = 8192  # It was 1024 abd increased it 8192 because of errno input overflowed
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 44100
    RECORD_SECONDS = 2
    WAVE_OUTPUT_FILENAME = "current_attempt.wav"
    p = pyaudio.PyAudio()

    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK)
    print("*****recording*****")

    frames = []

    for i in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
        data = stream.read(CHUNK, exception_on_overflow = False)
        frames.append(data)

    print("*****done recording*****")

    stream.stop_stream()
    stream.close()
    p.terminate()

    wf = wave.open(WAVE_OUTPUT_FILENAME, 'wb')
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(p.get_sample_size(FORMAT))
    wf.setframerate(RATE)
    wf.writeframes(b''.join(frames))
    wf.close()
    print "copied correctly"


def findfreq():
    chunk = 8192*2  # It was 2048 abd increased it 8192 because of errno input overflowed
    freqlist = []
    # open up a wave
    wf = wave.open('current_attempt.wav', 'rb')
    swidth = wf.getsampwidth()
    RATE = wf.getframerate()

    # use a Blackman window
    window = np.blackman(chunk)
    # open stream
    p = pyaudio.PyAudio()
    stream = p.open(format=
                    p.get_format_from_width(wf.getsampwidth()),
                    channels=wf.getnchannels(),
                    rate=RATE,
                    output=True)
    # read some data
    data = wf.readframes(chunk)
    # play stream and find the frequency of each chunk
    while len(data) == chunk * swidth:
        # write data out to the audio stream
        stream.write(data)
        # unpack the data and times by the hamming window
        indata = np.array(wave.struct.unpack("%dh" % (len(data) / swidth),
                                             data)) * window
        # Take the fft and square each value
        fftData = abs(np.fft.rfft(indata)) ** 2
        # find the maximum
        which = fftData[1:].argmax() + 1
        # use quadratic interpolation around the max
        if which != len(fftData) - 1:
            y0, y1, y2 = np.log(fftData[which - 1:which + 2:])
            x1 = (y2 - y0) * .5 / (2 * y1 - y2 - y0)
            # find the frequency and output it
            thefreq = (which + x1) * RATE / chunk
        else:
            thefreq = which * RATE / chunk
        # read some more data
        freqlist.append(thefreq)
        data = wf.readframes(chunk)
    if data:
        stream.write(data)

    stream.close()
    p.terminate()
    wf.close()  # These 3 might be the problem
    print "\r\n\r\nThe freq list is: " + str(freqlist)           
    if (max(freqlist) - min(freqlist)) < 40:
        print "avg freq = " + str(sum(freqlist) / len(freqlist))
        avg_freq = sum(freqlist) / len(freqlist)
        print avg_freq
        print "\r\n\r\n"
        return avg_freq
    print "r\n\r\n"
    return 0


def main():
    ser = start_arduino_connection()
    m = alsaaudio.Mixer("PCM")
    m.setvolume(0)
    language = choose_language_version()
    pick_sound_file(language, "start")  # Finds the correct one and plays it
    while True:
        if not check_door_status_and_first_riddle(ser):
            continue
        record()
        if 550 < findfreq() < 650: #and check_door_status_and_first_riddle(ser):
            break
    print "Correct sound from the thermoacoustic engine GOOD JOB!!"
    pick_sound_file(language, "end")


if __name__ == '__main__':
    main()
