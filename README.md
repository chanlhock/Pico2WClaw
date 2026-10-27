# :mouse: Welcome to Pico2WClaw

<p align="center">
 <img src="resources/pico2wclaw-logo.png" width="400">
</p>

<p align="center">
<i>Out of clutter, find Simplicity. From discord, find Harmony.<br> In the middle of difficulty lies Opportunity.</i><br><br>
&nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp;
&nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp;
&nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp;
&nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; ― Albert Einstein
</p> 

## Table of Contents
- [Description](#scroll-description)
- [Development Platform](#computer-development-platform)
- [Software Development](#floppy_disk-software-development)
- [Platform Tested](#iphone-platform-tested)
- [Screenshots](#film_strip-screenshots)
- [Buy Me a Coffee](#coffee-buy-me-a-coffee)
- [License](#page_with_curl-license)
- [Feedback and Suggestions](#speech_balloon-feedback-and-suggestions)

## :scroll: Description
Development of a small Autonomous AI Agent in Raspberry Pi Pico 2 W. \
The program runs on Raspberry Pi Pico 2 W.

## :computer: Development Platform
I have tested on Raspberry Pi Pico 2 W running Thonny. It may also work on Raspberry Pi Pico W.

On the Raspberry Pi Pico 2 W:
1. Do ensure that the Raspberry Pi Pico W is flashed with the correct *.uf2 file
2. The RPI_PICO_W-20251209-v1.27.0.uf2 file can be downloaded from DeepSeek folder in this repository.
3. Open Thonny and upload the files, ble.py and ssd1306.py in the repository folder /RPi Pi Pico W BLE onto Raspberry Pi Pico W. Program is written in MicroPython.
4. Open the file ble.py
5. Run ble.py. The following output will be displayed in the Thonny run window.

Note: You can rename ble.py to main.py so that the program will automatically run when Raspberry Pi Pico W power up.
~~~~
MPY: soft reboot
Initializing BLE...
Registering services...
Service registered, handle: 9
Advertising as 'Joystick_Pico'

~~~~
6. Raspberry Pi Pico W is now ready and accepting command from Hermes Agent running on the MacBook Air 2017. 

On the MacBook Air 2017:
1. Open Thonny and upload all the files in the repository folder DeepSeek/Pi5game onto Raspberry Pi 5. Program is using MicroPython.
2. Open the file Pi5_Space_Invaders_Bluetooth_Fast.py
3. Run Pi5_Space_Invaders_Bluetooth_Fast.py

## :floppy_disk: Software Development:
I have two systems, one in MacBook Air 2017 and the other in Raspberry Pi Pico W. 

On Raspberry Pi Pico W, there would be Micropython code that:
- pin assigned below:
- GP20 -> SDA (SSD1306 OLED)
- GP21 -> SCL (SSD1306 OLED)
- communicate with MacBook Air 2017 through Bluetooth.
- Accepts command from Hermes Agent to turn ON or OFF onboard LED
- OLED SSD1306 8 lines displays: 
  first line (button pressed status), second line joystick x and third line joystick y axis

    
## :iphone: Platform tested:
I have tested my code on:
- MacBook Air 2017 with Sequioa MacOS running Thonny with Raspberry Pi Pico 2 W

## :film_strip: Screenshots
<p float="left">
  <img src="resources/system-block-diagram.png" width="600" />
</p>
<p float="left">
  <img src="resources/gesture_landmarks.jpg" width="600" />
</p>

## :coffee: Buy Me a Coffee
If you appreciate my work, do support me by...<br>
<a href="https://www.buymeacoffee.com/chanlhock" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/default-yellow.png" alt="Buy Me A Coffee" height="41" width="174"></a>

## :page_with_curl: License
```
This program is licensed under the GNU General Public License v3.0 
Permissions of this strong copyleft license are conditioned on making  
available complete source code of licensed works and modifications,  
which include larger works using a licensed work, under the same  
license. Copyright and license notices must be preserved. Contributors  
provide an express grant of patent rights.
```
See the [GNU General Public License](LICENSE) for more details.

## :speech_balloon: Feedback and Suggestions
For any feedback or suggestions, feel free to contact me via email:\
:email: chanlhock@gmail.com :mouse:

