# Open and validate the Power BI report

1. Run the pipeline and report builder from the repository README.
2. In Power BI Desktop, open `powerbi/Retail.pbip`. Enable Power BI project support in Desktop options if your installation requests it.
3. Refresh the report to import the CSVs. The generated `DataFolder` parameter points to this clone's processed data directory.
4. Check the unfiltered overview against these controls: gross sales £9,655,544.63, credits £304,597.42, net sales £9,350,947.21 and 18,957 orders.
5. Select United Kingdom. Net sales must become £7,902,009.63 and orders 17,157. Clear the country filter afterwards.
6. On Customer repeat purchasing, verify 4,293 buyers, 2,742 repeat buyers and a repeat share of 63.9%.
7. On Monthly repurchase cohorts, verify the 2010-12 row at month age 1 is 36.5%. November 2011 has only month zero, not a zero-valued future month.
8. Inspect all four pages for clipped labels, table scrolling, filter interactions and currency formatting. Save a local PBIX only after these checks pass.

Native Desktop import and DAX execution have passed 19,318 SQL comparisons. The [native evidence](native_validation.json) records the checked populations and input fingerprints. The [project validation](project_validation.json) distinguishes structural, native calculation and visual delivery checks; changed inputs invalidate previous evidence. Static SQL previews are separate analytical images.

All four pages have also been reviewed in Desktop and in the native PDF export. The local `powerbi/RetailPortfolio.pbix` contains the imported data. The [delivery record](delivery_validation.json) records its checksum, the reviewed report definition and the PDF checksum. The [gallery](dashboard_gallery.md) shows the exported pages.

The first two pages use a country filter on the star schema. The last two use fixed-window SQL outputs, with no country/date filter. This distinction is intentional and stated in each page's subtitle.

The large product and customer tables can be scrolled. The matrix contains only observed cohort ages. Monthly labels are ISO strings, which sort chronologically. Monetary measures are in GBP, although Desktop regional settings can change displayed separators.

After Desktop saves the project as TMDL, keep those local edits. The builder refuses to overwrite an existing TMDL definition directory. Running the builder with `--overwrite` on its original TMSL project deliberately replaces model and report edits.
