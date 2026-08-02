# Prices per 1M tokens

The first rate group is the standard tier; the second is the priority tier.
The benchmark executor profiles pin the standard tier in their immutable
`price_catalog_id` and use it for local estimates. Provider-billed cost remains
unavailable for subscription runs.

| Model | Standard input | Standard cached input | Standard cache writes | Standard output | Priority input | Priority cached input | Priority cache writes | Priority output |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| gpt-5.6-sol | $5.00 | $0.50 | $6.25 | $30.00 | $10.00 | $1.00 | $12.50 | $45.00 |
| gpt-5.6-terra | $2.00 | $0.20 | $2.50 | $12.00 | $4.00 | $0.40 | $5.00 | $18.00 |
| gpt-5.6-luna | $0.20 | $0.02 | $0.25 | $1.20 | $0.40 | $0.04 | $0.50 | $1.80 |
