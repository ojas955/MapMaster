# MapMaster

MapMaster is a React + D3 geography guessing game where you identify countries from their map outline.

## Features

- Random country outline each round
- Guess input with instant feedback
- Score tracking
- Hint button that progressively reveals the country name
- Give up / next-round flow support

## Tech Stack

- React (Create React App)
- D3 Geo (`d3-geo`, via `d3`)
- GeoJSON dataset in `public/countries.geo.json`

## Run Locally

1. Install dependencies:

	```bash
	npm install
	```

2. Start development server:

	```bash
	npm start
	```

3. Open in browser:

	`http://localhost:3000`

## Available Scripts

- `npm start` – Run the app in development mode
- `npm test` – Run test watcher
- `npm run build` – Build optimized production bundle

## Project Structure

- `src/App.js` – Main game logic and UI
- `public/countries.geo.json` – Country geometry dataset
