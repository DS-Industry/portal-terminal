#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Конфигурация Modbus TCP для OWEN PLC
Содержит настройки регистров и константы функций автомойки
"""

# Константы функций автомойки
FUNCTIONS = {
    0: "Нет",
    1: "Химия 1", 
    2: "Химия 2",
    3: "Пена",
    4: "Ополаскивание",
    5: "Осмос",
    6: "Воск",
    7: "Сушка"
}

# Адреса Modbus регистров (проверенные рабочие настройки)
REGISTERS = {
    # Программы мойки
    'Program1': {
        'address': 0,
        'count': 15,
        'description': 'Программа 1'
    },
    'Program2': {
        'address': 35,
        'count': 15,
        'description': 'Программа 2'
    },
    'Program3': {
        'address': 70,
        'count': 15,
        'description': 'Программа 3'
    },
    'Program4': {
        'address': 105,
        'count': 15,
        'description': 'Программа 4'
    },
    'Program5': {
        'address': 140,
        'count': 15,
        'description': 'Программа 5'
    },
    
    # Цены программ
    'Price1': {
        'address': 30,
        'description': 'Цена Программы 1'
    },
    'LoyaltyPrice1': {
        'address': 31,
        'description': 'Цена по лояльности Программы 1'
    },
    'Price2': {
        'address': 65,
        'description': 'Цена Программы 2'
    },
    'LoyaltyPrice2': {
        'address': 66,
        'description': 'Цена по лояльности Программы 2'
    },
    'Price3': {
        'address': 100,
        'description': 'Цена Программы 3'
    },
    'LoyaltyPrice3': {
        'address': 101,
        'description': 'Цена по лояльности Программы 3'
    },
    'Price4': {
        'address': 135,
        'description': 'Цена Программы 4'
    },
    'LoyaltyPrice4': {
        'address': 136,
        'description': 'Цена по лояльности Программы 4'
    },
    'Price5': {
        'address': 170,
        'description': 'Цена Программы 5'
    },
    'LoyaltyPrice5': {
        'address': 171,
        'description': 'Цена по лояльности Программы 5'
    },
    'StartProgram1': {
        'address': 0,
    },
    'StartProgram2': {
        'address': 1,
    },
    'StartProgram3': {
        'address': 3,
    },
    'StartProgram4': {
        'address': 4,
    },
    'StartProgram5': {
        'address': 5,
    },
    #Купюрник
    'Cash': {
        'address': 16388,
        'description': 'Наличное внесение'
    }
}

# Настройки опроса
POLLING_INTERVALS = {
    'prices': 60,
    'programs': 60,
    'status': 60
}
