import requests

def test_dolarapi():
    try:
        response = requests.get("https://ve.dolarapi.com/v1/dolares/oficial", timeout=5)
        print("DolarAPI Status Code:", response.status_code)
        print("DolarAPI Response:", response.text)
    except Exception as e:
        print("DolarAPI Error:", e)

def test_bcv():
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        response = requests.get("https://www.bcv.org.ve/", headers=headers, verify=False, timeout=8)
        print("BCV Status Code:", response.status_code)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.content, 'html.parser')
        dolar_div = soup.find('div', id='dolar')
        if dolar_div:
            valor_text = dolar_div.find('strong').text.strip()
            print("BCV dolar value text:", valor_text)
        else:
            print("BCV div id='dolar' not found")
    except Exception as e:
        print("BCV Error:", e)

test_dolarapi()
test_bcv()
