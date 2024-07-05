import httpx
import logging
from fastapi import UploadFile

class APIService:
    def __init__(self, login_url, groups_url, login_data):
        self.client = httpx.AsyncClient()
        self.login_url = login_url
        self.groups_url = groups_url
        self.login_data = login_data
        self.token = None
        self.headers = {'Content-Type': 'application/json'}

    async def update_token(self):
        response = await self.client.post(self.login_url, json=self.login_data, headers=self.headers)
        if response.status_code == 200:
            self.token = response.json().get('access_token')
            self.headers['Authorization'] = f'Bearer {self.token}'
            logging.info('JWT token updated successfully.')
        else:
            logging.error(f'Failed to update JWT token: {response.status_code} - {response.text}')

    async def get_groups(self):
        if not self.token:
            await self.update_token()
        response = await self.client.get(self.groups_url, headers=self.headers)
        response.raise_for_status()
        return response.json()

    async def get_group_details(self, group_id):
        if not self.token:
            await self.update_token()
        response = await self.client.get(f"{self.groups_url}/{group_id}", headers=self.headers)
        response.raise_for_status()
        return response.json()

    async def submit_ticket(self, ticket_data, photo: UploadFile = None):
        if not self.token:
            await self.update_token()
        if photo:
            files = {'photo': (photo.filename, photo.file, photo.content_type)}
            response = await self.client.post('http://95.174.92.220:8000/tickets', data=ticket_data, files=files, headers=self.headers)
        else:
            response = await self.client.post('http://95.174.92.220:8000/tickets', data=ticket_data, headers=self.headers)
        return response

    async def check_active_ticket(self, tg_chat):
        if not self.token:
            await self.update_token()
        response = await self.client.get(f'http://95.174.92.220:8000/tickets/{tg_chat}/active', headers=self.headers)
        response.raise_for_status()
        return response.json()

    async def search_faq(self, query):
        if not self.token:
            await self.update_token()
        faq_data = {'message': query}
        response = await self.client.post('http://95.174.92.220:8000/faqs/search', json=faq_data, headers=self.headers)
        response.raise_for_status()
        return response.json()
