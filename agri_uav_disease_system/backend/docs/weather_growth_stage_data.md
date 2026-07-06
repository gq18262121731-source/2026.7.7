# Weather And Growth Stage Data

Weather data is manually recorded in Stage 6.1. No real weather API is connected.

Weather endpoints:
- `POST /api/weather/observations`
- `GET /api/weather/observations`

Growth stage endpoints:
- `POST /api/growth-stages`
- `GET /api/growth-stages/plots/{plot_id}`

Growth stage supports manual correction and basic inference from sowing or transplanting date. Manual growth stage takes priority over inferred growth stage.

Prediction currently uses:
- Recent humidity.
- Recent rainfall.
- Current growth stage.

Missing weather or growth stage records do not cause prediction failure.
