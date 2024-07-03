# NoAuth

NoAuth is a simple OpenID Connect Identity Provider to use in testing. The authorization screen allows you to enter whatever values you want for the claims that will populate the ID Token.

> [!CAUTION]
> This is to be used for testing only. Do NOT use in production.

## Quickstart

Local:

```sh
pdm run fastapi dev noauth/main.py
```

Docker:

```sh
docker run --rm -it -v "$(pwd)/config.toml:/usr/src/app/noauth.toml:z" -p 8080:80 ghcr.io/dbluhm/noauth:latest
```

## Demo

```sh
cd demo
docker-compose build
docker-compose up
```

Navigate to http://localhost:8888 to open up WordPress demo site. Set up the instance with an admin user.

After setup, login as the admin user. Add a new plugin, searching for "oidc." The first result will most likely be "OAuth Single Sign On - SSO (OAuth Client)" by miniOrange. Install this plugin and activate it. This will take you to a page with a table of active plugins.

Click "Configure" under the new plugin

On the plugin configuration page, select "Add New Application" and then select "Custom OpenID Connect App"

Set the App name as desired, e.g. "noauth"

Leave the callback URL as http://localhost:8888.

Set the client ID (any value is fine).

Set the client secret (any value is fine).

Add "openid" to scopes.

Set the Authorization endpoint to `http://localhost:8080/oidc/authorize`.

Set the token endpoint to `http://noauth:8080/oidc/token`.

Hit next. On the Summary page, check the `Body` check box under "Send client credentials in"

Hit Finish. This will bring up the authorization page where you can submit the defaults or modify values as desired.

After hitting submit, you should see a "Test completed successfully screen" with a summary of the contents of the ID token.

You can now sign out of the admin user and try signing in with the noauth provider.

## Configuration

See `default.noauth.toml` for a sample configuration file. Adjust as desired.

If running locally, copy this file to `noauth.toml`. If running with docker, insert this file by build or volume into the container's working directory as `noauth.toml`.
