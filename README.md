# dia-tap-xero

This is Dialogue's [Singer](https://singer.io) tap that produces JSON-formatted data from Xero
following the [Singer spec](https://github.com/singer-io/getting-started/blob/master/SPEC.md).

This tap:

- Pulls raw data from Xero's [API](https://developer.xero.com/documentation/)
- Extracts the following resources from Xero
  - [Bank Transactions](https://developer.xero.com/documentation/api/banktransactions)
  - [Contacts](https://developer.xero.com/documentation/api/contacts)
  - [Credit Notes](https://developer.xero.com/documentation/api/credit-notes)
  - [Invoices](https://developer.xero.com/documentation/api/invoices)
  - [Manual Journals](https://developer.xero.com/documentation/api/manual-journals)
  - [Overpayments](https://developer.xero.com/documentation/api/overpayments)
  - [Prepayments](https://developer.xero.com/documentation/api/prepayments)
  - [Purchase Orders](https://developer.xero.com/documentation/api/purchase-orders)
  - [Journals](https://developer.xero.com/documentation/api/journals)
  - [Accounts](https://developer.xero.com/documentation/api/accounts)
  - [Bank Transfers](https://developer.xero.com/documentation/api/bank-transfers)
  - [Employees](https://developer.xero.com/documentation/api/employees)
  - [Expense Claims](https://developer.xero.com/documentation/api/expense-claims)
  - [Items](https://developer.xero.com/documentation/api/items)
  - [Payments](https://developer.xero.com/documentation/api/payments)
  - [Receipts](https://developer.xero.com/documentation/api/receipts)
  - [Users](https://developer.xero.com/documentation/api/users)
  - [Branding Themes](https://developer.xero.com/documentation/api/branding-themes)
  - [Contact Groups](https://developer.xero.com/documentation/api/contactgroups)
  - [Currencies](https://developer.xero.com/documentation/api/currencies)
  - [Organisations](https://developer.xero.com/documentation/api/organisation)
  - [Repeating Invoices](https://developer.xero.com/documentation/api/repeating-invoices)
  - [Tax Rates](https://developer.xero.com/documentation/api/tax-rates)
  - [Tracking Categories](https://developer.xero.com/documentation/api/tracking-categories)
  - [Linked Transactions](https://developer.xero.com/documentation/api/linked-transactions)
- Outputs the schema for each resource
- Incrementally pulls data based on the input state

## Running the tap

1) Create config file with the following variables and store it at `./config.json`:
```
{
  "client_id": "SECRET",
  "client_secret": "SECRET",
  "tenant_id": "SECRET",
  "refresh_token": "GENERATED BY NOTEBOOK",
  "start_date": "2000-01-01"
}
```

1.1) The secrets are all stored in 1Password in the Analytics DB Credentials Vault

1.2) Using those secrets and the jupyter notebook called `get_initial_xero_tokens`, run through the web-based auth process to get your initial refresh token. Using this token the tap will then chain your tokens and will be able to run on its own. You must use the notebook manually before every run of the tap. See more on this OAuth protocol [here](https://developer.xero.com/documentation/oauth2/auth-flow).

2) Run `poetry update` to ensure dependencies are up to date

3) Run `poetry install` to add these to your machine

4) Run `poetry shell` to enter the virtual environment from which you can run tap-xero

5) Run `python dia_tap_xero/__init__.py -c config.json -p properties.json > out.json` to run this tap to an output json file

5.1) Run `python dia_tap_xero/__init__.py -c config.json -p properties.json | target-postgres -c config_postgres.json` to run this tap to a table in a postgres DB. Ensure that singer-target-postgres is installed to do this and ensure that as to its spec, your config_postgres.json is properly configured.


## Authentication

Xero's new [Oauth2 Authentication flow](https://developer.xero.com/documentation/oauth2/auth-flow) requires in-browser authentication to first produce a refresh and an access token, followed by a chaining of those tokens to keep them valid.

Access tokens have a Time To Live (TTL) of 30 minutes. Refresh tokens have a TTL of 30 days. Thus, to keep the chain valid, the refresh token must be used at least once every 30 days.

### Starting the Chain of Tokens
1. Ensure you are in the appropriate AWS region (`ca-central-1` for dev, or `us-east-1` for prod)
2. Launch Jupyter Notebooks and open `get_initial_xero_tokens.ipynb`
3. Fill in the credentials for this account (which can be found in 1Password)
4. Run the first cell to define the function
5. Run the second cell and log in to Xero and accept the authorizaiton
6. Copy the URL once redirected back to dialogue.co into the textbox in the notebook and submit
7. The function will then return the new tokens and write the refresh token to AWS SSM Parameter Store. Now when you go to run the tap, via Airflow or the CLI, it will call to AWS to fetch this key from SSM Parameter Store. 
