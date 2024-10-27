# vortex-thunder
bite my shiny metal ass! (status: `non-functional`)

## requirements

- python 3.x
- see [reqs](requirements.txt)

## installation

1. install dependencies

   ```bash
   pip install -r requirements.txt
   ```

2. set environment variables

   ensure you have the following environment variables set:

   - `NEXUS_API_KEY`: your nexus mods api key
   - `THUNDERSTORE_API_KEY`: your thunderstore api key

   you can set them in your terminal session like this:

   ```bash
   export NEXUS_API_KEY='your_nexus_api_key'
   export THUNDERSTORE_API_KEY='your_thunderstore_api_key'
   ```

## usage

```bash
python main.py
```

## configuration

ensure your browser (firefox or chromium) is running to allow `browser_cookie3` to fetch session cookies.

## notes

- the script uses `browser_cookie3` to retrieve your `nexusmods_session` cookie from your active browser session.
- make sure your session cookie is valid; if it expires, refresh session / restart browser and rerun.

## license

[ this project is licensed under the MIT license ]