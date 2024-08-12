
# TODO: Implement data fetching utilities. [Milestone: Data Integration]

import requests

class DataFetcher:
    @staticmethod
    def fetch_game_data(api_url):
        response = requests.get(api_url)
        return response.json()