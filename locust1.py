from locust import HttpUser, task, between
import random
import string

# def random_url():
#     """Генерирует случайную длинную URL для тестирования"""
#     return "https://example.com/" + "".join(random.choices(string.ascii_letters + string.digits, k=10))

class ShortenerUser(HttpUser):
    wait_time = between(1, 3)  # Ждём от 1 до 3 секунд между запросами

    @task
    def create_short_link(self):
        """Отправляет запрос на создание короткой ссылки через query-параметры"""
        long_url = "https://en.wikipedia.org/wiki/Chamath_Palihapitiya"
        response = self.client.post(f"/links/shorten?original_url={long_url}")

        if response.status_code == 201:
            short_code = response.json().get("short_code")
            print(f"✅ Создана ссылка: {long_url} -> {short_code}")
        else:
            print(f"❌ Ошибка {response.status_code}: {response.text}")
