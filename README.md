# Firefighter

SmokeDetector v2.0: finds spamminess / trash in new questions and answers on Stack Exchange, and posts it to a chatroom for quick killing with fire

## Setup Instructions:

Same as [SmokeDetector](https://github.com/Charcoal-SE/SmokeDetector):

    git clone https://github.com/Charcoal-SE/SmokeDetector.git
    cd SmokeDetector
    git submodule init
    git submodule update
    sudo pip install beautifulsoup
    sudo pip install requests --upgrade
    sudo pip install websocket-client
