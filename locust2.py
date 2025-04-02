from locust import HttpUser, task, between

class RedirectUser(HttpUser):
    wait_time = between(1, 3)  # Ждём 1-3 секунды между запросами
    short_code = "d15a9027"  # Используй реальный short_code из базы

    @task
    def test_redirect(self):
        """Тестирует редирект по короткой ссылке"""
        with self.client.get(f"/links/{self.short_code}", allow_redirects=False, catch_response=True) as response:
            if response.status_code == 307:
                response.success()
            else:
                response.failure(f"Unexpected status code: {response.status_code}")

