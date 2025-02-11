# Haper-Server

This is the RESTful API server of haper, built with the Flask web framework.

---


## Requirements

To get started, ensure you have the following installed:

- Python 3.7 (or a compatible version).

### DB and other storage resource requirement

- Postgresql
- AWS SQS
- Google Cloud PUB/SUB

## Usage

1. This project use python-dotenv to load runtime envs. First create your own .env file to the root of this project
   ```text
   APP_NAME=haper
   JWT_AUTH_SECRET=<your own secret for signing jwt token>
   JWT_AUTH_COOKIE_NAME=<the cookie name for the jwt token>
   LOG_LEVEL=<log level, DEBUG for test, INFO for production>
   POSTGRES_DSN=<your postgresql db dsn>
   ALLOW_ORIGINS=<list of allow origins for CORS, separate by comma>
   ```

2. Run the application:

   ```bash
   python app.py
   ```


Replace the above command with the appropriate entry point script if your project uses a different one.

---

## File Structure

```text
.
├── app.py
├── biz # business logic
│   ├── controller # controller level
│   ├── dal # the directory to put db model and model operation functions
│   ├── handler # api endpoints define 
│   │   ├── middleware # router middlewares
│   │   └── user # user related API
│   │   └── ... # other APIs
│   ├── service # the directory for accessing external service, like db, mq etc.
│   └── utils # the directory for some utility functions
├── tests # the directory where to write unit test and integration test
├── requirements.txt
└── app.py # the main entry point for this project
```

---

## Contributing

Contributions to this project are welcome! If you'd like to contribute:

1. Fork the repository.
2. Create a new branch for your feature or bug fix.
3. Commit your changes and push the branch.
4. Open a pull request for discussion and review.

---

## License

This project is licensed under the [AGPL License](LICENSE). Feel free to use and modify it as needed.
