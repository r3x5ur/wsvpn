# Websocket VPN

> use websocket forward local port
> Encrypted transmission
> Connection authentication

## using

1. server side

```bash
git clone https://github.com/r3x5ur/wsvpn.git
cd wsvpn
docker-compose up -d
```

2. client side

```bash
git clone https://github.com/r3x5ur/wsvpn.git
cd wsvpn
python -m venv venv
# active venv
pip install websockets pycryptodome
python app.py client
```
