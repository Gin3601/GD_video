# AI Video Factory Feishu Widget

This is a Feishu cloud document widget for the FastAPI service in the parent project.

## Configure

Edit `app.json` before uploading:

```json
{
  "appID": "cli_xxx",
  "blockTypeID": "blk_xxx"
}
```

`appID` comes from Feishu Open Platform. `blockTypeID` is generated after enabling the cloud document widget capability.

The widget stores the backend API URL in browser local storage. During local development it defaults to:

```text
http://localhost:8000
```

For production, set it in the widget settings to your public HTTPS FastAPI origin.

## Develop

```bash
npm install
npm start
```

## Build

```bash
npm run build
```

## Upload

Install and log in to the Feishu developer CLI first:

```bash
npm install @lark-opdev/cli@latest -g
npm run opdev:login
```

Then upload from this directory:

```bash
npm run upload
```

This runs `opdev upload dist -t Block -v 1.0.0 -d initial`, which uploads the built cloud document widget package.

After uploading, go to Feishu Open Platform, select the uploaded package, fill in the widget information, create an app version, and submit it for release.
