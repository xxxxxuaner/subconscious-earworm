import uos
import machine

# SD card configuration
sd = machine.SDCard(slot=3, width=1,
                    sck=machine.Pin(7),
                    mosi=machine.Pin(9),
                    miso=machine.Pin(8),
                    cs=machine.Pin(21))

# Mount the SD card
uos.mount(sd, '/sd')

# Write a file
with open('/sd/hello.txt', 'w') as f:
    f.write('Hello, SD card!')

# Read the file
with open('/sd/hello.txt', 'r') as f:
    print(f.read())

# List SD contents
print(uos.listdir('/sd'))