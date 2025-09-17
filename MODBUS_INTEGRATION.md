# Modbus TCP Integration для OWEN PLC

Этот документ описывает интеграцию Modbus TCP клиента для управления роботизированной автомойкой через OWEN PLC.

## 📁 Структура файлов

```
orders/
├── modbus_client.py                    # Основной Modbus TCP клиент
├── modbus_integration_example.py       # Примеры интеграции с системой
├── management/
│   └── commands/
│       └── test_modbus.py             # Django команда для тестирования
test_modbus.py                         # Независимый тестовый скрипт
```

## 🔧 Установка зависимостей

Добавьте в `requirements.txt`:
```
pymodbus==3.5.2
```

Установите зависимости:
```bash
pip install -r requirements.txt
```

## ⚙️ Настройка

### 1. Переменные окружения

Добавьте в `.env` файл:
```env
# Modbus TCP настройки для OWEN PLC
MODBUS_HOST=192.168.1.100
MODBUS_PORT=502
MODBUS_TIMEOUT=10
```

### 2. Django настройки

Настройки уже добавлены в `config/settings.py`:
```python
# Modbus TCP настройки для OWEN PLC
MODBUS_HOST = os.getenv('MODBUS_HOST', '192.168.1.100')
MODBUS_PORT = int(os.getenv('MODBUS_PORT', '502'))
MODBUS_TIMEOUT = int(os.getenv('MODBUS_TIMEOUT', '10'))
```

## 🚀 Использование

### 1. Базовое использование

```python
from orders.modbus_client import OwenPLCCarWash

# Создание клиента
plc = OwenPLCCarWash(host='192.168.1.100', port=502)

# Подключение
if plc.connect():
    # Чтение статуса мойки
    status = plc.get_wash_status()
    print(f"Статус: {status['status_text']}")
    
    # Запуск программы 1
    plc.start_wash_program(1)
    
    # Отключение
    plc.disconnect()
```

### 2. Интеграция с системой

```python
from orders.modbus_integration_example import get_car_wash_controller

# Получение контроллера
controller = get_car_wash_controller()

# Инициализация подключения
if controller.connect():
    # Проверка занятости
    is_busy = controller.is_car_wash_busy()
    
    # Запуск мойки для заказа
    success = controller.start_car_wash(order)
    
    # Ожидание завершения
    controller.wait_for_completion(timeout=300)
```

## 🧪 Тестирование

### 1. Django команда

```bash
# Базовый тест
python manage.py test_modbus

# Тест с кастомными параметрами
python manage.py test_modbus --host 192.168.1.200 --port 502

# Полный тест с чтением всех данных
python manage.py test_modbus --full-test
```

### 2. Независимый скрипт

```bash
python test_modbus.py
```

### 3. Программное тестирование

```python
from orders.modbus_client import test_modbus_connection

# Тест подключения
if test_modbus_connection('192.168.1.100', 502):
    print("✅ Подключение работает!")
```

## 📊 Modbus регистры

### Основные регистры

| Регистр | Адрес | Описание |
|---------|-------|----------|
| setProgramm1 | %QW12 | Настройки программы 1 (15 регистров) |
| setProgramm2 | %QW47 | Настройки программы 2 (15 регистров) |
| quantity_CeckleProgramm1 | %QW27 | Количество повторений программы 1 |
| GVL_Price1 | %QW42 | Цена программы 1 |
| LoyalityPrice1 | %QW43 | Цена по программе лояльности |
| start_wash | %QW100 | Команда запуска мойки |
| wash_status | %QW101 | Статус мойки |
| current_program | %QW102 | Текущая программа |
| wash_progress | %QW103 | Прогресс мойки (%) |

### Функции автомойки

| Код | Функция |
|-----|---------|
| 0 | Нет |
| 1 | Химия 1 |
| 2 | Химия 2 |
| 3 | Пена |
| 4 | Ополаскивание |
| 5 | Осмос |
| 6 | Воск |
| 7 | Сушка |

### Статусы мойки

| Код | Статус |
|-----|--------|
| 0 | Свободна |
| 1 | Готовится к запуску |
| 2 | Выполняется |
| 3 | Завершена |
| 4 | Ошибка |
| 5 | Остановлена |

## 🔄 Интеграция с существующей системой

### Замена симуляции на реальное управление

В файле `orders/start_carwash.py` можно заменить:

```python
# Старый код (симуляция)
def _run_wash(order_id: int):
    # ... симуляция мойки ...
    time.sleep(60)  # 60 секунд симуляции

# Новый код (реальное управление)
def _run_wash(order_id: int):
    from orders.modbus_integration_example import get_car_wash_controller
    
    controller = get_car_wash_controller()
    order = WashOrder.objects.get(id=order_id)
    
    # Запуск реальной мойки
    if controller.start_car_wash(order):
        # Ожидание завершения
        controller.wait_for_completion(timeout=300)
    else:
        # Обработка ошибки
        order.status = WashOrder.Status.FAILED
        order.save()
```

### Обновление проверки занятости

В файле `orders/queue_option.py`:

```python
# Старый код
def is_car_wash_busy() -> bool:
    return WashOrder.objects.filter(status=WashOrder.Status.PROCESSING).exists()

# Новый код
def is_car_wash_busy() -> bool:
    from orders.modbus_integration_example import get_car_wash_controller
    
    controller = get_car_wash_controller()
    if controller.connected:
        return controller.is_car_wash_busy()
    else:
        # Fallback к старой логике
        return WashOrder.objects.filter(status=WashOrder.Status.PROCESSING).exists()
```

## 🛠️ Расширение функциональности

### Добавление новых регистров

В `modbus_client.py` добавьте в `REGISTERS`:

```python
REGISTERS = {
    # ... существующие регистры ...
    'new_register': {
        'start_address': 200,
        'description': 'Новый регистр'
    }
}
```

### Добавление новых функций

```python
def new_function(self):
    """Новая функция для работы с PLC"""
    # Ваш код здесь
    pass
```

## 🚨 Обработка ошибок

### Автоматические fallback

Система автоматически переключается на существующую логику при ошибках Modbus:

```python
def is_car_wash_busy(self) -> bool:
    if not self.connected:
        # Fallback к существующей логике
        return WashOrder.objects.filter(status=WashOrder.Status.PROCESSING).exists()
    
    try:
        return self.plc.is_wash_busy()
    except Exception as e:
        logger.error(f"Ошибка Modbus: {e}")
        # Fallback к существующей логике
        return WashOrder.objects.filter(status=WashOrder.Status.PROCESSING).exists()
```

### Логирование

Все операции логируются с соответствующими уровнями:

```python
logger.info("✅ Команда запуска программы 1 отправлена")
logger.error("❌ Не удалось подключиться к OWEN PLC")
logger.warning("⚠️ Modbus не подключен, используем fallback проверку")
```

## 📝 Примеры использования

### 1. Мониторинг статуса мойки

```python
from orders.modbus_integration_example import monitor_wash_status

# В фоновой задаче
monitor_wash_status()
```

### 2. Управление очередью

```python
from orders.modbus_integration_example import get_car_wash_controller

controller = get_car_wash_controller()
if not controller.is_car_wash_busy():
    # Мойка свободна, можно запускать следующий заказ
    next_order = get_next_order_from_queue()
    controller.start_car_wash(next_order)
```

### 3. Чтение программ мойки

```python
from orders.modbus_client import OwenPLCCarWash

plc = OwenPLCCarWash('192.168.1.100')
if plc.connect():
    programs = plc.read_all_programs()
    print(f"Программа 1: {programs['setProgramm1']['functions']}")
    plc.disconnect()
```

## 🔧 Отладка

### Включение подробного логирования

```python
import logging
logging.getLogger('orders.modbus_client').setLevel(logging.DEBUG)
```

### Проверка подключения

```python
from orders.modbus_client import test_modbus_connection

if test_modbus_connection('192.168.1.100', 502):
    print("✅ Подключение работает")
else:
    print("❌ Проблемы с подключением")
```

## 📋 Чек-лист интеграции

- [ ] Установлен pymodbus
- [ ] Настроены переменные окружения
- [ ] Протестировано подключение к PLC
- [ ] Протестированы все функции
- [ ] Настроено логирование
- [ ] Добавлены fallback механизмы
- [ ] Протестирована интеграция с системой
- [ ] Настроен мониторинг статуса
- [ ] Протестирована обработка ошибок

## 🆘 Устранение неполадок

### Проблема: Не удается подключиться к PLC

**Решение:**
1. Проверьте IP-адрес и порт
2. Убедитесь что PLC доступен в сети
3. Проверьте настройки файрвола
4. Проверьте логи: `tail -f modbus_test_*.log`

### Проблема: Команды не выполняются

**Решение:**
1. Проверьте правильность адресов регистров
2. Убедитесь что PLC находится в режиме записи
3. Проверьте права доступа к регистрам

### Проблема: Fallback не работает

**Решение:**
1. Проверьте что существующая логика работает
2. Убедитесь что модели импортированы правильно
3. Проверьте логи на наличие ошибок

## 📞 Поддержка

При возникновении проблем:

1. Проверьте логи системы
2. Запустите тестовые команды
3. Проверьте подключение к PLC
4. Обратитесь к документации OWEN PLC
