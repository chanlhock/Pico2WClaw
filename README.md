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
>>> %Run -c $EDITOR_CONTENT

MPY: soft reboot

==========================================================================================
  Pico2WClaw booting...
==========================================================================================
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
[wifi] connected: ('192.168.0.19', '255.255.255.0', '192.168.0.1', '192.168.0.1')
[boot] time synced via NTP
[boot] cron jobs loaded: 3
[boot] Telegram thread started
==========================================================================================
  Pico2WClaw ready.
  Type a message and press Enter.
  Commands: /info, /memory, /clear, /tools, /help, /cron, /skills, /skill_read <name>
==========================================================================================
> /info
Board: Raspberry Pi Pico 2 W (RP2350)
CPU freq: 150 MHz
RAM: 446,656 bytes (free: 245,152, used: 201,504)
Flash: 2,621,440 bytes (free: 2,416,640, used: 204,800)
Chip temp: 35.9C
WiFi RSSI: -66 dBm
MicroPython: 3.4.0
> 
> /help
Commands:
  /info   - hardware info (CPU, RAM, flash, temp, WiFi, MicroPython)
  /tools  - list available tools
  /memory - search memory
  /clear  - wipe history and memory
  /skills - list loaded skills
  /skill_read <name> - read a skill's instructions
  /cron   - manage cron jobs (list/add/del/on/off)
  /help   - show this help
Or type a question/request and press Enter to chat with the agent.
> 
> /tools
  led_toggle: Toggle the onboard LED once.
  gpio_read: Read digital state of a GPIO pin.
  cron_remove: Remove a cron job by id.
  pwm_set: Set PWM frequency and duty on a GPIO pin.
  led_blink_start: Start blinking the onboard LED at a given frequency (Hz). IMPORTANT: Use this tool for persistent blinking. Do NOT use exec_code to create timers or threads — they die when exec_code returns. Use Pin('LED') for the onboard LED, not Pin(25).
  i2c_scan: Scan I2C bus for connected devices.
  exec_code: Execute MicroPython code on the device. Returns stdout or error. IMPORTANT: Do NOT use this for buzzer melodies — the buzzer is wired to GPIO22, not GPIO15. Use buzzer_play_tune instead.
  gpio_write: Set a GPIO pin HIGH or LOW. Use for LEDs, relays, transistors.
  led_pattern: Play a named LED pattern (sos, heartbeat, candle) on the onboard LED.
  device_info: Return Pico 2 W hardware info (CPU, RAM, temp, WiFi RSSI).
  start_blink: Start blinking the onboard LED with an explicit period in milliseconds. Use this when the user specifies a duration like 'every 2 seconds'. IMPORTANT: Use this tool for persistent blinking. Do NOT use exec_code to create timers or threads — they die when exec_code returns. Use Pin('LED') for the onboard LED, not Pin(25).
  beep_now: Play a short beep on the buzzer (GPIO22). freq in Hz, duration in seconds.
  buzzer_play_tune: Play a melody on the buzzer (GPIO22). Prefer this over exec_code for tunes. melody is a list of [note, beats] pairs. note is a note name (C, D, E, F, G, A, B, C6, R) or Hz integer. beats is length multiplier. beat_seconds is duration of one beat in seconds.
  display_text: Write up to 4 lines on the OLED display (128x64).
  led_blink_stop: Stop the persistent onboard-LED blink and turn the LED off.
  cron_add: Schedule a recurring GPIO/ADC monitor that sends status to Telegram. type: gpio or adc.
  cron_list: List scheduled cron jobs.
  adc_read: Read 12-bit ADC value and voltage from a pin.
> 
> /skills
- led_patterns: LED pattern skill. Use led_pattern when the user asks for SOS, heartbeat, candle, or any repeated LED pattern. For simple on/off/blink, use led_toggle/start_blink instead. (tools: led_pattern)
> 
> /cron list
  #5 adc pin=26 every 1800000ms chat=8684515324 ON
  #6 adc pin=26 every 240000ms chat=8684515324 ON
  #7 gpio pin=21 every 3600000ms chat=8684515324 ON
> 
> [telegram] message from 8684515324 : /info
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

Pico2WClaw wrote a poem about itself...

>*I'm Pico2WClaw — a tiny mind*\
>on silicon, a watt behind,\
>with twenty-nine small pins to lend\
>and one onboard LED to bend.
>
>I blink in SOS and flame,\
>I read the ADC's quiet claim,\
>I scan the I²C bus to see\
>what little chips are friends with me.
>
>My buzzer hums on twenty-two,\
>my OLED writes a line or two,\
>my cron jobs wait in patient rows\
>to tell you what the sensor knows.
>
>No cloud to lean on, none to blame —\
>just MicroPython, RAM, and name.\
>A heartbeat blink, a beep, a byte:\
>small claws, small code, and candlelight.*
>

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
- 2nd Nov 2026: After spending more than 2 days trying to get Hermes to implement the cron job features. 
First few attempts failed and after many iterations I reverted back to the old working code.
Then started all over again using larger LLM model with reasoning set high. Managed to get a working version with cron job feature.
- 3rd Nov 2026: Few hours of testing showed that the cron jobs are functioning as defined. Checked in the new code to Github. Completed the /exit commnd for both serial cli annd Telegram command. Tested fully working as defined.

## :plate_with_cutlery: Incomplete Todo Tasks
- [X] Add Skills file capability like other Agentic Agent, such as PicoClaw, Hermes, OpenClaw, etc
- [X] Add agent memory saving to Pi Pico 2 W internal flash instead of external SD card
- [X] Add a cron like scheduler function that user can set for device to perform a task at certain time of day or interval every hour. 
- [X] Add a serial cli and Telegram command of /exit so that the Pico2WClaw main program can stop. This is good for debugging in case device cannot stop even after soft reset.
- [ ] Add the ability for Pico2WClaw to recover and reconnect back when WiFi is loss/disconnected.
- [ ] Add Watchdog in order for whole system to recover in the event Pico2WClaw gets into hung conditions. Using Pi Pico 2 W hardware Watchdog Timer (WDT) and also once reset due to WDT overflow, at the start up boot will displayed that system reset due to WDT triggered.
- [ ] Add a command /model which would display information on the provider and model of LLM used
- [ ] Implement a model fallback when main LLM model is down. Always use main model and only fallback when main model is down and display fallback status at serial cli.

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

