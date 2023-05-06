import pygame
from pynput.keyboard import Key, Controller as KeyboardController

pygame.init()
joystick = pygame.joystick.Joystick(0)
joystick.init()

keyboard = KeyboardController()

pressed = False
start_button = False
select_button = False

while True:
    for event in pygame.event.get():
        if event.type == pygame.JOYBUTTONDOWN:
            if event.button == 7:  # Xbox Start button
                start_button = True
            elif event.button == 6:  # Xbox Select button
                select_button = True
        elif event.type == pygame.JOYBUTTONUP:
            if event.button == 7:  # Xbox Start button
                start_button = False
            elif event.button == 6:  # Xbox Select button
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
