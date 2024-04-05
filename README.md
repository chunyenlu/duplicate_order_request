# Duplicate Order Requests Report


This script creates a daily report for order order request duplicates. Order request duplicates
are defined as follows:
  - lower case of both patient first name and last name are the same and neither are empty
  - within the same product id
  - more than 1 orders are found with 30 day range back track from the report date

The report can be run by specifying the year and month, data for each day within the month is added in separate tabs.
For the current month, the report would generate daily reports till the prior day

The report can also be generated for a specific date only

The Excel generation portion is based on Ben Tarr's original Django implementation

To run the script:
1. Establish tunnel to website clone:
   ssh -4NL 5432:clone-db.awsphi.counsyl.com:5432 clone-web-phi.counsyl.com
2. Ttart Django Shell-Plus session for website: make shell
3. pip install any missing packages: i.e ColorHash
4. Copy and paste the entire script
5. Uncomment the last lines to generate the report for the current month
6. To run previous months' reports, use: generate_daily_report_for_month(year, month).
   
   -- A month Excel file "duplicates-{month_name}-sql.xlsx is generated
7. To run a daily report, use: generate_daily_report(year, month, day).
   
   -- A daily Excel file "duplicates-{year}-{month}-{day}-sql.xlsx is generated, Notice that the value for year, month, day are all in numbers


# SQL for the report

The SQL is defined with multiple CTE (Common Table Expressions) for maintainability
and performance. The SQL can be run within 10 seconds

By default the date ranges for searching duplication is 30 days. To extend the day range
substitute the number "30" in the first 2 CTE's, recent_or_with_patients,or_and_dups_in_range

CTE definitions:

recent_or_with_patients:

    All order requests with neither patient last name nor first name for the last 30 days,
    each OR record is amended with date interval from its previous duplicate instance if found,
    also with last created date for each duplicate sets
    
or_and_dups_in_range:

    find Count of duplicates for ORs in the last 30 days with duplicates
    
dups_ors_for_the_day:

    Retrieve all duplicates OR sets with its last instance of duplicate located in the report date
    
order_request_patch_info:

    Retrieve created_id and tkpc count from order request patches for each OR
    
salesforce_ids:

    Get list of salesforce ids for a matching clinic id from an OR
    
vendors:

    Get list of vendors for a matching clinic id from an OR
    
barcode_count:

    Get the number of barcodes for the OR's in the last 30 days with a matching clinic id
    
sample_count:

    Get sample count based on the converted order of an OR

