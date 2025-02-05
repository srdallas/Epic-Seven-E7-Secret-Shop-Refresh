import subprocess
import os
from io import BytesIO
import time
import csv

from PIL import Image
import threading
import cv2
import numpy as np
import keyboard

import random

class E7Item:
    def __init__(self, image=None, price=0, count=0):
        self.image=image
        self.price=price
        self.count=count

    def __repr__(self):
        return f'ShopItem(image={self.image}, price={self.price}, count={self.count})'

class E7Inventory:
    def __init__(self):
        self.inventory = dict()

    def addItem(self, path:str, name='', price=0, count=0):
        image = cv2.imread(os.path.join('adb-assets', path))
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        newItem = E7Item(image, price, count)
        self.inventory[name] = newItem

    def getStatusString(self):
        status_string = ''
        for key, value in self.inventory.items():
            status_string += key[0:4] + ': ' + str(value.count) + ' '
        return status_string

    def getName(self):
        res = []
        for key in self.inventory.keys():
            res.append(key)
        return res
    
    def getCount(self):
        res = []
        for value in self.inventory.values():
            res.append(value.count)
        return res
    
    def getTotalCost(self):
        sum = 0
        for value in self.inventory.values():
            sum += value.price * value.count
        return sum

    def writeToCSV(self, duration, skystone_spent):
        duration = round(duration, 2)

        res_folder = 'ShopRefreshHistory'
        if not os.path.exists(res_folder):
            os.makedirs(res_folder)

        history_file = 'ADB_History.csv'

        path = os.path.join(res_folder, history_file)
        if not os.path.isfile(path):
            with open(path, 'w', newline='') as file:
                writer = csv.writer(file)
                column_name = ['Duration', 'Skystone spent', 'Gold spent']
                column_name.extend(self.getName())
                writer.writerow(column_name)
        with open(path, 'a', newline='') as file:
            writer = csv.writer(file)
            data = [duration, skystone_spent, self.getTotalCost()]
            data.extend(self.getCount())
            writer.writerow(data)

class E7ADBShopRefresh:
    def __init__(self, tap_sleep:float = 0.5, budget=None):
        self.loop_active = False
        self.end_of_refresh = True
        self.tap_sleep = tap_sleep
        self.budget = budget
        self.refresh_count = 0
        self.keyboard_thread = threading.Thread(target=self.checkKeyPress)
        self.adb_path = os.path.join('adb-assets','platform-tools', 'adb')
        self.storage = E7Inventory()
        self.screenwidth = 1920
        self.screenheight = 1080
        self.updateScreenDimension()

        self.storage.addItem('cov.jpg', 'Covenant bookmark', 184000)
        self.storage.addItem('mys.jpg', 'Mystic medal', 280000)
        #self.storage.addItem('fb.jpg', 'Friendship bookmark', 18000)

    def start(self):
        self.loop_active = True
        self.end_of_refresh = False
        self.keyboard_thread.start()
        self.refreshShop()

    #threads
    def checkKeyPress(self):
        while(self.loop_active and not self.end_of_refresh):
            self.loop_active = not keyboard.is_pressed('esc')
        self.loop_active = False
        print('Shop refresh terminated!')

    def refreshShop(self):
        self.clickShop()
        #time needed for item to drop in after refresh (0.8)
        sliding_time = 1
        #stat track
        start_time = time.time()
        milestone = self.budget//10
        #swipe location
        x1 = str(0.6250 * self.screenwidth + random.randint(-15,5))
        y1 = str(0.6481 * self.screenheight + random.randint(-5,15))
        y2 = str(0.4629 * self.screenheight + random.randint(-8,15))
        #refresh loop
        while self.loop_active:

            time.sleep(sliding_time)
            brought = set()

            if not self.loop_active: break
            #look at shop (page 1)
            screenshot = self.takeScreenshot()
            #print(len(self.storage.inventory.items()))
            for key, value in self.storage.inventory.items():
                pos = self.findItemPosition(screenshot, value.image)
                if pos is not None:
                    self.clickBuy(pos)
                    value.count += 1
                    brought.add(key)

            if not self.loop_active: break
            #swipe
            adb_process = subprocess.run([self.adb_path, 'shell', 'input', 'swipe', x1, y1, x1, y2])
            #wait for action to complete
            time.sleep(0.5)

            if not self.loop_active: break
            #look at shop (page 2)
            screenshot = self.takeScreenshot()
            for key, value in self.storage.inventory.items():
                pos = self.findItemPosition(screenshot, value.image)
                if pos is not None and key not in brought:
                    self.clickBuy(pos)
                    value.count += 1

            #print every 10% progress
            if self.budget >= 30 and self.refresh_count*3 >= milestone:
                clear = ' ' * 30
                print(clear, end='\r')
                print(f'{int(milestone/self.budget*100)}% {self.storage.getStatusString()}', end='\r')
                milestone += self.budget//10
            
            if not self.loop_active: break
            if self.budget:
                if self.refresh_count >= self.budget//3:
                    break

            self.clickRefresh()
            self.refresh_count += 1
        
        self.end_of_refresh = True
        self.loop_active = False
        if self.refresh_count*3 != self.budget: print('100%') 
        duration = time.time()-start_time
        self.storage.writeToCSV(duration=duration, skystone_spent=self.refresh_count*3)
        self.printResult()
    
    #helper function
    def printResult(self):
        print('\n---Result---')
        for key, value in self.storage.inventory.items():
            print(key, ':', value.count)
        print('Skystone spent:', self.refresh_count*3)

    def updateScreenDimension(self):
        adb_process = subprocess.run([self.adb_path, 'exec-out', 'screencap','-p'], stdout=subprocess.PIPE)
        byte_image = BytesIO(adb_process.stdout)
        pil_image = Image.open(byte_image)
        pil_image = np.array(pil_image)
        y, x, _ = pil_image.shape
        self.screenwidth = x
        self.screenheight = y


    def takeScreenshot(self):
        adb_process = subprocess.run([self.adb_path, 'exec-out', 'screencap','-p'], stdout=subprocess.PIPE)
        byte_image = BytesIO(adb_process.stdout)
        pil_image = Image.open(byte_image)
        pil_image = np.array(pil_image)
        screenshot = cv2.cvtColor(pil_image, cv2.COLOR_BGR2GRAY)
        # ims = cv2.resize(screenshot, (960, 540))
        # cv2.imshow('image window', ims)
        # cv2.waitKey(0)
        # cv2.destroyAllWindows()
        return screenshot

    def findItemPosition(self, screen_image, item_image):
        result = cv2.matchTemplate(screen_image, item_image, cv2.TM_CCOEFF_NORMED)
        loc = np.where(result >= 0.75)

        if loc[0].size > 0:
            x = loc[1][0] + self.screenwidth * 0.4718
            y = loc[0][0] + self.screenheight * 0.1000
            pos = (x, y)
            return pos
        return None

    #macro
    def clickShop(self):
        #newshop
        x = self.screenwidth * 0.0411 + random.randint(-5,5)
        y = self.screenheight * 0.2935 + random.randint(-5,5)
        adb_process = subprocess.run([self.adb_path, 'shell', 'input', 'tap', str(x), str(y)])
        time.sleep(self.tap_sleep)

        #oldshop
        x = self.screenwidth * 0.4406 + random.randint(-5,5)
        y = self.screenheight * 0.2462 + random.randint(-5,5)
        adb_process = subprocess.run([self.adb_path, 'shell', 'input', 'tap', str(x), str(y)])
        time.sleep(self.tap_sleep)

        #newshop
        x = self.screenwidth * 0.0411 + random.randint(-5,5)
        y = self.screenheight * 0.2935 + random.randint(-5,5)
        adb_process = subprocess.run([self.adb_path, 'shell', 'input', 'tap', str(x), str(y)])
        time.sleep(self.tap_sleep)

    def clickBuy(self, pos):
        if pos is None:
            return False
        
        x, y = pos
        adb_process = subprocess.run([self.adb_path, 'shell', 'input', 'tap', str(x), str(y)])
        time.sleep(self.tap_sleep)

        #confirm
        x = self.screenwidth * 0.5677 + random.randint(-5,5)
        y = self.screenheight * 0.7037 + random.randint(-5,5)
        adb_process = subprocess.run([self.adb_path, 'shell', 'input', 'tap', str(x), str(y)])
        time.sleep(self.tap_sleep)
        time.sleep(0.5)
    
    def clickRefresh(self):
        x = self.screenwidth * 0.1698 + random.randint(-5,5)
        y = self.screenheight * 0.9138 + random.randint(-5,5)
        adb_process = subprocess.run([self.adb_path, 'shell', 'input', 'tap', str(x), str(y)])
        time.sleep(self.tap_sleep)

        if not self.loop_active: return
        #confirm
        x = self.screenwidth * 0.5828 + random.randint(-5,5)
        y = self.screenheight * 0.6111 + random.randint(-5,5)
        adb_process = subprocess.run([self.adb_path, 'shell', 'input', 'tap', str(x), str(y)])
        time.sleep(self.tap_sleep)


if __name__ == '__main__':

    #intro
    print('Epic Seven Shop Refresh with ADB')
    print('Before launching this application')
    print('Make sure Epic Seven is opened and that ADB is turned on')
    print('Ingame resolution should be set to 1920 x 1080')
    print('(relaunch this application if the above conditions are not met)')
    print()
    input('when you finish reading, press enter to continue!')
    print()

    #settings
    try:
        tap_sleep = float(input('Tap sleep(in seconds) recommand 0.5: '))
    except:
        print('invalid input, default to tap sleep of 0.5 second')
        tap_sleep = 0.5
    try:
        budget = float(input('Amount of skystone that you want to spend:'))
    except:
        print('invalid input, default to 1000 skystone budget')
        budget = 1000
    print()
    if budget >= 1000:
            ev_cost = 1691.04536 * int(budget) * 2
            ev_cov = 0.006602509 * int(budget) * 2
            ev_mys = 0.001700646 * int(budget) * 2
            print('Approximation(EV) based on current budget:')
            print(f'Cost: {int(ev_cost):,} (make sure you have at least this much gold)')
            print(f'Cov: {ev_cov:.1f}')
            print(f'mys: {ev_mys:.1f}')
            print()
    input('Press enter to start!')
    print('Press Esc to terminate anytime!')
    print()
    print('Progress:')
    ADBSHOP = E7ADBShopRefresh(tap_sleep=tap_sleep, budget=budget)
    ADBSHOP.start()
    print()
    input('press enter to exit...')