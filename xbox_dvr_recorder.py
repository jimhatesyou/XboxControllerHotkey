import os
import pygame
import time
import msvcrt
from pynput.keyboard import Key, Controller as KeyboardController

# ANSI escape color codes
RESET = "\033[0m"
GRAY = "\033[90m"
GREEN = "\033[92m"
RED = "\033[91m"

# ASCII splash screen
ascii_art = r'''
              %%%%%%%%%%%%              
                   %%                   
      %%                        %%%     
   %%%%%%%%%%              %%%%%%%%%%   
  %%%%%%%%%%                %%%%%%%%%%  
 %%%%%%%%%                    %%%%%%%%% 
%%%%%%%%          %%%%          %%%%%%%%%
%%%%%%%        %%%%%%%%%%        %%%%%%%
 %%%%       %%%%%%%%%%%%%%%%       %%%% 
  %%      %%%%%%%%%%%%%%%%%%%%      %%  
   %    %%%%%%%%%%%%%%%%%%%%%%%%    %   
       %%%%%%%%%%%%%%%%%%%%%%%%%%       
         %%%%%%%%%%%%%%%%%%%%%%         
               %%%%%%%%%%               
'''

# Show splash screen
os.system("cls")
print(ascii_art)
time.sleep(3)
os.system("cls")

# Initialize
pygame.init()
keyboard = KeyboardController()
pressed = False
start_button = False
select_button = False
controller_connected = False
joystick = None

def show_ui(connected: bool):
    os.system("cls")
    print(f"{GRAY}XboxControllerHotkey v1.25{RESET}\n")

    if connected:
        print(f"{GREEN}Controller connected.{RESET}\n")
        print()
        print("You are ready to play!")
        print()
        print("Leave this window open while playing to capture clips")
        print("with Back + Start on your controller (via GameBar).")
        print()
        print("Feel free to minimize this program.")
        print("For updates check github.com/jimhatesyou")
        print()
        print()
        print(f"{GRAY}Press ESC to close.{RESET}")
        print()
        print()
    else:
        print(f"{RED}Controller not detected. Connect controller to continue.{RESET}\n")

# Continuously poll until connected
while not controller_connected:
    show_ui(False)
    if pygame.joystick.get_count() > 0:
        try:
            joystick = pygame.joystick.Joystick(0)
            joystick.init()
            controller_connected = True
            show_ui(True)
        except Exception:
            controller_connected = False
    else:
        time.sleep(3)

# Main loop
while True:
    if msvcrt.kbhit() and ord(msvcrt.getch()) == 27:  # ESC key
        print("\nExiting...")
        break

    # Detect disconnection
    if pygame.joystick.get_count() == 0 and controller_connected:
        controller_connected = False
        joystick = None
        start_button = False
        select_button = False
        show_ui(False)

    # Detect reconnection
    elif pygame.joystick.get_count() > 0 and not controller_connected:
        try:
            joystick = pygame.joystick.Joystick(0)
            joystick.init()
            controller_connected = True
            show_ui(True)
        except Exception:
            controller_connected = False

    for event in pygame.event.get():
        if event.type == pygame.JOYBUTTONDOWN:
            if event.button == 7:
                start_button = True
            elif event.button == 6:
                select_button = True
        elif event.type == pygame.JOYBUTTONUP:
            if event.button == 7:
                start_button = False
            elif event.button == 6:
                select_button = False

    if start_button and select_button:
        if not pressed:
            keyboard.press(Key.alt_l)
            keyboard.press(Key.cmd)
            keyboard.press('g')
            keyboard.release('g')
            keyboard.release(Key.cmd)
            keyboard.release(Key.alt_l)
            pressed = True
    else:
        pressed = False

    pygame.time.wait(10)
