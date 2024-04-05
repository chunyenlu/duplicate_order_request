# duplicate_order_request


This script creates a daily report for order order request duplicates. The order request duplicates
are defined as follows:
  - lower case of both patient first name and last name are the same and neither are empty
  - within the same product id
  - more than 1 orders are found with 30 day range back track from the report date

The report can be run by specifying the year and month, data for each day within the month is added in separate tabs.
For the current month, the report would generate daily reports till the prior day

The report can also be generated for a specific dayte only

The Excel generation portion is based on Ben Tarr's original Django implementation

To run the script:
1. Establish tunnel to website clone
   ssh -4NL 5432:clone-db.awsphi.counsyl.com:5432 clone-web-phi.counsyl.com
2. start Django Shell-Plus session for website: make shell
3. pip install any missing packages: i.e ColorHash
4. Copy and paste the entire script
5. uncomment the last lines to generate the report for the current month
6. run previous months' reports with generate_daily_report_for_month(year, month)
   A month Excel file "duplicates-{month_name}-sql.xlsx is generated
7. run daily report with generate_daily_report(year, month, day)
   A daily Excel file "duplicates-{year}-{month}-{day}-sql.xlsx is generated
   --Notice that the value for year, month, day are all in numbers
