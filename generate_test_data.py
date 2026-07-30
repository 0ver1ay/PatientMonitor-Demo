"""
Скрипт для генерации тестовых данных за 6 часов
Запустите этот скрипт перед первым запуском приложения для создания истории данных
"""
from utils.data_storage import DataStorage

if __name__ == '__main__':
    print("Генерация тестовых данных за 6 часов...")
    storage = DataStorage()
    storage.generate_test_data(hours=6)
    print("Тестовые данные успешно созданы в файле patient_data.json")
    print("Теперь можно запускать приложение: py main.py")













