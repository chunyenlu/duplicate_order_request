#
# This script creates a daily report for order order request duplicates. The order request duplicates
# are defined as follows:
# - lower case of both patient first name and last name are the same and neither are empty
# - within the same product id
# - more than 1 orders are found with 30 day range back track from the report date
#
# The report can be run by specifying the year and month,
# data for each day within the month is added in separate tabs.
# For the current month, the report would generate daily reports till the prior day
#
# The report can also be generated for a specific dayte only
#
# The Excel generation portion is based on Ben Tarr's original Django implementation
#
# To run the script:
# 1. Establish tunnel to website clone
#    ssh -4NL 5432:clone-db.awsphi.counsyl.com:5432 clone-web-phi.counsyl.com
# 2. start Django Shell-Plus session for website: make shell
# 3. pip install any missing packages: i.e ColorHash
# 4. Copy and paste the entire script
# 5. uncomment the last lines to generate the report for the current month
# 6. run previous months' reports with generate_daily_report_for_month(year, month)
#    A month Excel file "duplicates-{month_name}-sql.xlsx is generated
# 7. run daily report with generate_daily_report(year, month, day)
#    A daily Excel file "duplicates-{year}-{month}-{day}-sql.xlsx is generated
#    --Notice that the value for year, month, day are all in numbers
#
import calendar
import string
from datetime import datetime, timedelta

import pandas
from colorhash import ColorHash

from counsyl.product.ordering.schema.enums import ORDER_FLOW

#
# This is the list of raw fields report is based on. These would be further refined for the
# Excel columns
#
FIELDS = [
    "patient_first_name",  # excel omission of the names is hacky for now, it removes by column index
    "patient_last_name",  # Thus inserting fields before these causes issue for now.
    "patient_dob",
    "id",
    "accession_id",
    "requisition_number",
    "barcode",
    "created_at",
    "clinic_id",
    "clinic_external_id",
    "salesforces",
    "clinic_name",
    "clinic_barcode_volume",
    "clinic_emr_enabled_on",
    "created_by_id",
    "vendors",
    "product_id",
    "product_name",
    "test_offering_names",
    "order_flow",
    "tkpc",
    "order_sample_count",
    "converted",
]

#
#   The function further processing the raw data to generate final Excel columns
#
def style_orderrequest_df(df, field_order=None, show_names=False, for_excel=False):
    """
    Creates a styled pandas dataframe from a list of OrderRequest values.
    """
    LT_GRAY = "#cccccc"
    LT_GREEN = "#a6ffb3"
    LT_BLUE = "#a6fcff"
    LT_RED = "#ffa6b2"
    LT_ORANGE = "#ffb52b"
    LT_PINK = "#ffe8ff"

    # Reindex to get the appropriate order of the columns
    if field_order is not None:
        df = df.reindex(columns=field_order)

    # Strip time zone
    if "created_at" in df:
        df["created_at"] = df["created_at"].apply(
            lambda created_at: created_at.tz_convert(None)
        )

    # Rename converted column to have values of "converted" or "not converted"
    if "converted" in df:
        df["converted"] = df["converted"].apply(
            lambda converted: "converted" if converted else "not converted"
        )

    # Convert id field into link for the OrderRequest
    if "id" in df:
        format_string = (
            '=HYPERLINK("https://internal.counsyl.com/helpdesk/ordering/orderrequest/{id}", "{id}")'
            if for_excel
            else "{id}"
        )

        df["id"] = df["id"].apply(lambda id: format_string.format(id=id))

    # Convert clinic external ids into links and drop clinic_id
    if "clinic_id" in df and "clinic_external_id" in df:
        format_string = (
            '=HYPERLINK("https://internal.counsyl.com/helpdesk/healthcare/clinic/{id}", "{external_id}")'
            if for_excel
            else "{external_id}"
        )

        df["clinic_external_id"] = df.apply(
            lambda row: format_string.format(
                id=int(row["clinic_id"]), external_id=row["clinic_external_id"]
            )
            if row["clinic_id"] > -1  # NaN easy check
            else None,
            axis=1,
        )

        df = df.drop(columns=["clinic_id"])

    # Convert clinic name into salesforce links and drop
    if "clinic_name" in df and "salesforces" in df:
        format_string = (
            '=HYPERLINK("https://myriadgenetics.my.salesforce.com/{id}", "{name}")'
            if for_excel
            else "{name}"
        )

        df["clinic_name"] = df.apply(
            lambda row: format_string.format(
                id=row["salesforces"].split(",")[-1],
                name=row["clinic_name"],
            )
            if row["clinic_name"] is not None
            else None,
            axis=1,
        )

        df = df.drop(columns=["salesforces"])

    # Convert barcode into link (for my I'm just setting the link to be a query parameter)
    if "barcode" in df:
        if not for_excel:
            df["barcode"] = df["barcode"].apply(
                lambda barcode: f"{barcode}"
                if barcode
                   is not None  # hacky, but NaN is not greater than a number, or less than
                else None
            )
        else:
            df["barcode"] = df["barcode"].apply(
                lambda
                    barcode: f'=HYPERLINK("https://internal.counsyl.com/helpdesk/my/child/?q={barcode}", "{barcode}")'
                if barcode
                   is not None  # hacky, but NaN is not greater than a number, or less than
                else None
            )

    # Convert the order flow slug raw data to display label similar to Django Enum field
    if "order_flow" in df:
        df["order_flow"] = df["order_flow"].apply(
            lambda
                order_flow: string.capwords(ORDER_FLOW(order_flow).name.replace("_", " "))
            if order_flow
            else None
        )

    if "patient_first_name" in df:
        df["patient_first_name"] = df["patient_first_name"].apply(
            lambda name: name[0] if len(name) > 0 else ""
        )

    if "patient_last_name" in df:
        df["patient_last_name"] = df["patient_last_name"].apply(
            lambda name: name[0] if len(name) > 0 else ""
        )

    fields_to_hide = (
        [
            "patient_first_name",
            "patient_last_name",
        ]
        if not show_names
        else []
    )

    # Background styling for various fields
    def style_from_name(firstname, lastname):
        # To keep the name hidden but identitfy orders with the same name, patient names
        # are hashed into a color and that color is used as the background.
        color = ColorHash(
            (firstname + lastname).lower(), lightness=[i / 100 for i in range(70, 100)]
        )
        return f"background-color: {color.hex}"

    def style_from_order_flow(order_flow):
        color = LT_BLUE if str(order_flow) == "Emr" else "white"
        return f"background-color: {color}"

    def style_from_patch_kit_count(count):
        if count is None:
            return f"background-color: {LT_GREEN}"
        elif count > 0:
            return f"background-color: {LT_RED}"
        else:
            return f"background-color: {LT_GREEN}"

    def style_from_converted(converted):
        color = LT_ORANGE if converted is "converted" else LT_PINK
        return f"background-color: {color}"

    def style_from_sample_count(count):
        if count:
            if count < 1:
                color = LT_GRAY
            elif count == 1:
                color = LT_GREEN
            else:
                color = LT_RED
        else:
            color = LT_RED
        return f"background-color: {color}"

    style = (
        df.style.apply(
            lambda row: [
                style_from_name(row.patient_first_name, row.patient_last_name)
                for _ in row
            ],
            axis=1,
        )
        .apply(
            lambda s: [style_from_order_flow(order_flow) for order_flow in s],
            subset="order_flow",
            axis=0,
        )
        .apply(
            lambda s: [style_from_patch_kit_count(count) for count in s],
            subset="tkpc",
            axis=0,
        )
        .apply(
            lambda s: [style_from_converted(converted) for converted in s],
            subset="converted",
            axis=0,
        )
        .apply(
            lambda s: [style_from_sample_count(sample_count) for sample_count in s],
            subset="order_sample_count",
            axis=0,
        )
        .hide_columns(fields_to_hide)
    )
    return style


def write_to_excel(writer, names_and_styles):
    START_COL = 0  # start col is set to 2 to skip patient name

    for name, style in names_and_styles:
        style.to_excel(writer, sheet_name=name, index=False, startcol=START_COL)


def dictfetchall(cursor):
    """
    Return all rows from a cursor as a dict.
    Assume the column names are unique.
    """
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def run_report(end_date, writer):
    """
    Use the defined SQL to generate raw data and feed it into Panda dataframe

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
    """
    print(f"Preparing Duplicates OR Report for {end_date}...")
    sql_query = """
    with recent_or_with_patients as (
        select oo1.*,
 --           lag(oo1.created_at, 1) over (partition by lower(oo1.patient_first_name), lower(oo1.patient_last_name), oo1.product_id order by created_at) as prev_date,
            max(oo1.created_at) over (partition by lower(oo1.patient_first_name), lower(oo1.patient_last_name), oo1.product_id) as last_created_date,
            coalesce((extract(epoch from (oo1.created_at - lag(oo1.created_at, 1) over (partition by lower(oo1.patient_first_name), lower(oo1.patient_last_name), oo1.product_id order by created_at)))/86400)::int, 0) as diff_date
        from ordering_orderrequest oo1
        where oo1.created_at > {end_date}::date - (30)
          and not (coalesce(patient_first_name, '') = '' or coalesce(patient_last_name, '') = '')
    ), or_and_dups_in_range as (
        select *,
               count(*) over (partition by patient_first_name, patient_last_name, product_id) as ct
        from recent_or_with_patients
        where diff_date <= 30
    ), initial_dups_ors_for_the_day as (
        select * from or_and_dups_in_range
        where ct > 1 and last_created_date::date = {end_date}::date
    ) ,or_info as (
        select dups.id as order_request_id,
            sum(case when orp.created_by_endpoint='/sales/transfer-kits/' then 1
                else 0
                end) as tkpc_ct,
            min(orp.id) as first_patch_id
        from initial_dups_ors_for_the_day dups
        left join ordering_orderrequestpatch orp on orp.order_request_id = dups.id
        group by 1
    ), patch_tests as (
        select
            id as patch_id,
            string_agg(test,';') as tests
        from (
            select
                patch.id,
                jsonb_array_elements(data::jsonb->'order_product'->'sub_products')->>'test_offering_name' as test
            from ordering_orderrequestpatch patch
            join or_info on patch.id = or_info.first_patch_id
            order by 1,2
        ) q
        group by 1
    ), order_request_patch_info as (
        select
            or_info.order_request_id,
            or_info.tkpc_ct,
            au.email as created_by_id,
            patch_tests.tests
        from or_info
        left join patch_tests on  patch_tests.patch_id = or_info.first_patch_id
        left join ordering_orderrequestpatch orp on orp.id = or_info.first_patch_id
        left join auth_user au on au.id = orp.created_by_id
    ), second_partition as (
        select *,
        max(created_at) over (partition by lower(patient_first_name), lower(patient_last_name), product_parititon_key) as last_created_at,
        count(*) over (partition by lower(patient_first_name), lower(patient_last_name), product_parititon_key) as sp_ct
        from (
            select dups.*,
            (case when op.slug = 'genesight' then op.name || patch_info.tests
                 else op.name
                 end) as product_parititon_key
            from initial_dups_ors_for_the_day dups
            join order_product op on op.id = dups.product_id
            left join order_request_patch_info patch_info on patch_info.order_request_id = dups.id
        ) q
    ), dups_ors_for_the_day as (
        select *
        from second_partition sp
        where sp.sp_ct > 1 and  sp.last_created_at::date = {end_date}::date
    ), salesforce_ids as (
    select
        clinic_id,
        string_agg(sid.salesforce_id,',') as salesforces
        from
        (
            select
                dup.clinic_id,
                csf.salesforce_id
            from dups_ors_for_the_day dup
            left join healthcare_clinic hc on hc.id = dup.clinic_id
            left join common_salesforceid csf on csf.object_id = hc.id
            left join django_content_type dct on dct.id = csf.content_type_id
            where dct.app_label = 'healthcare' and dct.model = 'clinic'\
            group by 1,2
        ) sid
        group by 1
    ), vendors as (
        select
            vn.clinic_id,
            string_agg(vn.vendor, ',') as vendors
        from (
            select
                dup.clinic_id,
                emr_v.name as vendor
            from dups_ors_for_the_day dup
            join emr_clinicemrsettings emr_c using (clinic_id)
            join emr_emrvendor emr_v on emr_v.id = emr_c.emr_vendor_id
            group by 1,2
        ) vn
        group by 1
    ), barcode_count as (
        select barcodes.order_request_id,
               count(*) as barcode_count
        from (
            select dup.id as order_request_id, oreq.barcode
                from dups_ors_for_the_day dup
                join recent_or_with_patients oreq on dup.clinic_id = oreq.clinic_id
                group by 1, 2
        ) barcodes
        group by 1
    ), sample_count as (
        select dup.id as order_request_id,
            count(*) as sample_count
        from dups_ors_for_the_day dup
        join order_order ord on ord.order_request_uuid = dup.uuid
        left join order_orderkit okit on okit.order_id = ord.id
        left join vendor_sample sample on sample.orderkit_id = okit.id
        group by 1
    )
    select
        patient_first_name,
        patient_last_name,
        patient_dob,
        g.id,
        g.accession_id,
        requisition_number,
        barcode,
        created_at,
        g.clinic_id,
        clinic.external_id as clinic_external_id,
        salesforces.salesforces,
        clinic.name as clinic_name,
        bc.barcode_count as clinic_barcode_volume,
        clinic.emr_enabled_on as clinic_emr_enabled_on,
        orp.created_by_id,
        orp.tests as test_offering_names,
        vendors.vendors,
        g.product_id,
        op.name as product_name,
        order_flow,
        coalesce(orp.tkpc_ct, 0) as tkpc,
        sc.sample_count as order_sample_count,
        odr.id is not null as converted
    from dups_ors_for_the_day g
    left join order_product op on op.id = g.product_id
    left join healthcare_clinic clinic on clinic.id = g.clinic_id
    left join vendors using(clinic_id)
    left join barcode_count bc on bc.order_request_id = g.id
    left join order_request_patch_info orp on orp.order_request_id = g.id
    left join salesforce_ids salesforces on salesforces.clinic_id = g.clinic_id
    left join sample_count as sc on sc.order_request_id = g.id
    left join order_order odr on odr.order_request_uuid = g.uuid
    order by g.product_id, patient_last_name, patient_first_name, created_at desc;
    """
    sql_query = sql_query.format(end_date=f"'{end_date}'")

    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute(sql_query)
        dups = dictfetchall(cursor)

    df = pandas.DataFrame(dups)

    style = style_orderrequest_df(
         df,
         field_order=FIELDS,
         for_excel=True,
    )

    write_to_excel(writer, [(f"{end_date}", style)])

def generate_daily_report_for_month(year, month):
    """
    Generate all daily report for all days in a month
    Each daily report is on an individual Excel sheet
    """
    days_in_month = calendar.monthrange(year, month)[1]

    current_time = datetime.utcnow()
    if year == current_time.year and month == current_time.month:
        days_in_month = current_time.day - 1

    path = f"duplicates-{calendar.month_name[month].lower()}-sql.xlsx"
    with pandas.ExcelWriter(path) as writer:
        for day in range(days_in_month, 0, -1):
            report_date = datetime(year, month, day).date()
            run_report(str(report_date), writer)


def generate_daily_report(year, month, day):
    """
    Generate daily report for a specific date
    """
    path = f"duplicates-{year}-{month}-{day}-sql.xlsx"
    with pandas.ExcelWriter(path) as writer:
        report_date = datetime(year, month, day).date()
        run_report(str(report_date), writer)


#current_time = datetime.utcnow()
#generate_daily_report_for_month(current_time.year, current_time.month)
