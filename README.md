# :mouse: Welcome to Pico2WClaw

<p align="center">
 <img src="resources/pico2wclaw-logo.png" width="400">
</p>

<p align="center">
<i>The intelligence of an AI is only as good as the model used.</i><br><br>
&nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp;
&nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp;
&nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp;
&nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; ― Bernard Chan
</p> 

## Table of Contents
- [Description](#scroll-description)
- [Development Platform](#computer-development-platform)
- [Software Development](#floppy_disk-software-development)
- [Platform Tested](#iphone-platform-tested)
- [Screenshots](#film_strip-screenshots)
- [Chronology of Development Events](#hourglass_flowing_sand-chronology-of-development-events)
- [Incomplete Todo Tasks](#plate_with_cutlery-incomplete-todo-tasks)
- [Buy Me a Coffee](#coffee-buy-me-a-coffee)
- [License](#page_with_curl-license)
- [Feedback and Suggestions](#speech_balloon-feedback-and-suggestions)

## :scroll: Description
Development of a small Autonomous AI Agent in Raspberry Pi Pico 2 W. \
The Micropython program runs on Raspberry Pi Pico 2 W. \
I called it Pico2WClaw. 

It takes in prompt from Telegram and then sent to Deepseek LLM through API, the response from Deepseek LLM will call up tools on the device to turn on GPIO, read ADC from sensors connected to Raspberry Pi 2 W and also write code to execute on the microcontroller. 🤭 \
Managed to get the initial version up and running with Hermes Agent help. One thing nice is that I can read all the Python code and understand how the agent is functioning. 😆🤗

More detail information about Pico2WClaw usage can be obtained here: [Pico2WClaw README](/pico2wclaw/README.md) 

Pico2WClaw detail technical documentation of how it works can be obtained here: [Pico2WClaw Docs](/resources/pico2wclaw_docs.md) 

## :computer: Development Platform
I have tested on Raspberry Pi Pico 2 W running Thonny. It may also work on Raspberry Pi Pico W.

On the Raspberry Pi Pico 2 W:
1. Do ensure that the Raspberry Pi Pico 2 W is flashed with the correct *.uf2 file
2. The RPI_PICO2_W-20260824-v1.29.0.uf2 file can be downloaded from resources folder in this repository.
3. Open Thonny and upload all the files in the repository folder /pico2wclaw onto Raspberry Pi Pico W. Program is written in MicroPython.
4. Open the file boot2.py
5. Run boot2.py. The following output will be displayed in the Thonny run window.

Note: You can rename boot2.py to boot.py so that the program will automatically run when Raspberry Pi Pico 2 W power up.
~~~~
MPY: soft reboot

==================================================
  Pico2WClaw booting...
==================================================
[wifi] connecting to chanhome 2.4GHz ...
[wifi] waiting... (1/20)
[wifi] waiting... (2/20)
[wifi] waiting... (3/20)
[wifi] waiting... (4/20)
[wifi] waiting... (5/20)
[wifi] waiting... (6/20)
[wifi] waiting... (7/20)
[wifi] waiting... (8/20)
[wifi] waiting... (9/20)
[wifi] waiting... (10/20)
[wifi] connected: ('192.168.0.24', '255.255.255.0', '192.168.0.1', '192.168.0.1')
[boot] time synced via NTP
[boot] Telegram polling started
==================================================
  Pico2WClaw ready.
  Type a message and press Enter.
  Commands: /info, /memory, /clear, /tools
==================================================
> /tools
/tools
  led_blink_start: Start blinking the onboard LED at a given frequency (Hz). IMPORTANT: Use this tool for persistent blinking. Do NOT use exec_code to create timers or threads — they die when exec_code returns. Use Pin('LED') for the onboard LED, not Pin(25).
  beep_now: Play a beep on the buzzer. freq in Hz, duration in seconds.
  pwm_set: Set PWM frequency and duty on a GPIO pin.
  gpio_read: Read digital state of a GPIO pin.
  device_info: Return Pico 2 W hardware info (CPU, RAM, temp, WiFi RSSI).
  exec_code: Execute MicroPython code on the device. Returns stdout or error.
  gpio_write: Set a GPIO pin HIGH or LOW. Use for LEDs, relays, transistors.
  i2c_scan: Scan I2C bus for connected devices.
  led_blink_stop: Stop the persistent onboard-LED blink and turn the LED off.
  display_text: Write up to 4 lines on the OLED display (128x64).
  start_blink: Start blinking the onboard LED with an explicit period in milliseconds. Use this when the user specifies a duration like 'every 2 seconds'. IMPORTANT: Use this tool for persistent blinking. Do NOT use exec_code to create timers or threads — they die when exec_code returns. Use Pin('LED') for the onboard LED, not Pin(25).
  adc_read: Read 12-bit ADC value and voltage from a pin.
  led_toggle: Toggle the onboard LED once.
> [telegram] message from 8684515324 : /tools
[telegram] message from 8684515324 : /info
/info
/info
Board: Raspberry Pi Pico 2 W (RP2350)
CPU freq: 150 MHz
RAM: ~512 KB
Flash: 4 MB
Chip temp: 35.9C
WiFi RSSI: -59 dBm
MicroPython: 3.4.0;
> 
~~~~
6. Raspberry Pi Pico 2 W is now ready and accepting command from either Telegram or Thonny serial cli. 

## :floppy_disk: Software Development:

On Raspberry Pi Pico 2 W, the Micropython code would run an autonomous Agentic AI which:
- pin assigned below:
	- GP20 -> SDA (SSD1306 OLED)
	- GP21 -> SCL (SSD1306 OLED)
	- GP25 (Onboard LED)
	- GP22 (Buzzer)
- communicate with MacBook Air 2017 through Thonny serial CLI.
- Accepts command from Telegram to turn ON or OFF onboard LED and do other stuffs
- OLED SSD1306 4 lines display setable through Telegram message to LLM
More detail information can be obtained from [Pico2WClaw README](/pico2wclaw/README.md)

## :iphone: Platform tested:
I have tested my code on:
- MacBook Air 2017 with Sequioa MacOS running Thonny with Raspberry Pi Pico 2 W

## :film_strip: Screenshots
Raspberry Pi Pico 2 W board running Pico2WClaw Agentic Agent.
<p float="left">
  <img src="resources/pico2wclaw-board.jpg" width="600" />
</p>

## :hourglass_flowing_sand: Chronology of Development Events
- 27th Oct 2026: Started this Pico2WClaw development to create an Agentic AI Agent that would run on resources limited Raspberry Pi Pico 2 W.<br>
Gotten this idea when I was helping my son develop his Final Year project. His project was sending gestures prompt to Hermes agent in his laptop.
Hermes then execute a Skills to send through BLE to ESP32 IoT device to turn on/off led.<br>
It was then I got the idea of why not directly put the Agentic AI Agent on the IoT device bypassing laptop Agent.<br>
Subsequently I did a search and found that there is an open source development of such Agent for ESP32 S3 but there is no available agent for Raspberry Pi Pico yet.<br>
The Pycoclaw project can be found at: https://github.com/jetpax/pycoclaw<br>
I used my Hermes agent to study Pycoclaw repository and create for me Micropython code that works for Raspberry Pi Pico 2 W.<br>
I also prompted Hermes that it can remove some of the functionality like MCP, cron job, etc given that Raspberry Pi Pico 2 W resource of 512kB RAM and 4MB Flash.<br>
- 29th Oct 2026: Initially the led flashing was not working correctly. Later Hermes fixed it by doing threading so that it doesn't affect the serial cli and Telegram polling.<br>
Completed debugging and the initial version of Pico2WClaw is fully functional as an autonomous Agentic AI Agent.
The DeepSeek LLM can generate Python code to execute on Pico2WClaw playing tune on the buzzer but it crashed with timeout error half way.
- 30th Oct 2026: Fixed the play tune to buzzer issues. In addition, added Skills file features for Pico2WClaw
- 31st Oct 2026: With Hermes help, fixed the memory writing to/loading from sdcard instead of Pi Pico 2 W flash memory. <br>
[Pico2WClaw README](/pico2wclaw/README.md) and [Pico2WClaw Docs](/resources/pico2wclaw_docs.md) had both been updated.
- 1st Nov 2026: 

## :plate_with_cutlery: Incomplete Todo Tasks
- [X] Add Skills file capability like other Agentic Agent, such as PicoClaw, Hermes, OpenClaw, etc
- [X] Add agent memory saving to Pi Pico 2 W internal flash instead of external SD card
- [ ] Add a command /model which would display information on the provider and model of LLM used
- [ ] Add a cron like scheduler function that user can set for device to perform a task at certain time of day or interval every hour. 
- [ ] Add a serial cli and Telegram command of /exit so that the Pico2WClaw main program can stop. This is good for debugging in case device cannot stop even after soft reset.

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

