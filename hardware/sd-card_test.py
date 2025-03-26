# import uos
# import machine

# # SD card configuration
# sd = machine.SDCard(slot=3, width=1,
#                     sck=machine.Pin(7),
#                     mosi=machine.Pin(9),
#                     miso=machine.Pin(8),
#                     cs=machine.Pin(21))

# # Mount the SD card
# uos.mount(sd, '/sd')

# # Write a file
# with open('/sd/hello.txt', 'w') as f:
#     f.write('Hello, SD card!')

# # Read the file
# with open('/sd/hello.txt', 'r') as f:
#     print(f.read())

# # List SD contents
# print(uos.listdir('/sd'))

import uos
import machine
import time

# SD card configuration
try:
    sd = machine.SDCard(slot=3, width=1,
                        sck=machine.Pin(7),
                        mosi=machine.Pin(9),
                        miso=machine.Pin(8),
                        cs=machine.Pin(21))
    
    # Add a small delay
    time.sleep(0.5)
    
    # Mount the SD card
    try:
        uos.mount(sd, '/sd')
    except OSError as e:
        print("Mount error, trying to unmount first:", e)
        try:
            uos.umount('/sd')
            time.sleep(0.1)
            uos.mount(sd, '/sd')
        except Exception as e:
            print("Remount failed:", e)
            raise

    print("SD card mounted successfully")
    print("SD contents:", uos.listdir('/sd'))

except Exception as e:
    print("SD card initialization failed:", e)
    raise