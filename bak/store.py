#!/usr/bin/python
# -*- coding: UTF-8 -*-
import os

def writeIntoFile(name, content):
    os.remove(name)
    file = open(name, 'w')
    file.write(content)
    file.close()

def appendIntoFile(name, content):
    file = open(name, 'a')
    file.write(content)
    file.close()

def readFromFile(name):
    file = open(name, 'r')
    str = file.read()
    return str

# filename = 'stocklist.txt'
# content = 'test'
# writeIntoFile(filename, content)
# print(readFromFile(filename))