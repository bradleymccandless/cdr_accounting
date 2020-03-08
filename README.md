# Design

Any SIP software compatible with https://github.com/areski/cdr-pusher stores CDRs to a local SQLite database and cdr-pusher ships them to a central TimescaleDB. Hypertable borders are bi-monthly. From there we can tag the call with a customer account and rate it using libphonenumber and one master rate table (with the most expensive possible charge for each calling area). I patched libphonenumber heavily with data from localcallingguide. Google wants us to sumbit these patches with official documentation from each telco. That is a fair chunk of work, but will make geolocating calls 99.9% accurate for everyone including Android users. 

I specifically chose *not* to use a rate table per customer for the following reasons:

- speed/efficiency/scalablity (cdr accounting slows exponentially with each custom rate table)
- value visibility (if a customer chose a plan to save money, show them on every bill how much money they saved!)
- call fraud detection should use the maximum possible value to trigger alerts

If a customer has a custom rate through specialized agreements or a promotional calling plan I used a diff rate table. Diff rate tables are much smaller since they only have to store differences between the master rate table. At the end of the billing cycle these savings are calculated againt the charges from the master (most expensive) rate table and itemized on the customer bill as discounts. 

This code is highly specific to one voip provider's requirements, but the basic design is proven to 400 simultaneous calls on four westmere cores, and generalizing it will happen the next time a voip provider needs a call accounting solution.
