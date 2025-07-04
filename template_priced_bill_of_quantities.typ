// PRICED BILL OF QUANTITIES TEMPLATE
// author: carlo pavan
// year: 2025


// custom cell styles
#let total-cell-style = (stroke: (top: 0.25pt + gray))
#let root-cost-cell-style = (
  stroke: (bottom: (dash: "dotted")), 
  fill: gray.transparentize(90%),
  align: bottom
)



#let euro(num) = {
  str(calc.round(float(num), digits: 2)) + " €"
}



#let unit_map = (
  "METRE": "m",
  "SQUARE_METRE": "m²",
  "m2": "m²",
  "CUBIC_METRE": "m³",
  "m3": "m³",
  "VOLUMEUNIT / CUBIC_METRE": "m³",
  "KILOGRAM": "kg",
  // add more mappings as needed
)



#let format-decimal(num, places: 2) = {
  let rounded = calc.round(num, digits: places)
  let str-num = str(rounded)
  
  // Split into integer and decimal parts
  let parts = str-num.split(".")
  let integer-part = parts.at(0)
  let decimal-part = parts.at(1, default: "")
  
  // Add thousand separators to integer part
  let formatted-integer = ""
  let chars = integer-part.clusters().rev()
  for (i, char) in chars.enumerate() {
    if i > 0 and calc.rem(i, 3) == 0 {
      formatted-integer = "'" + formatted-integer
    }
    formatted-integer = char + formatted-integer
  }
  
  // Ensure decimal part has correct number of places
  decimal-part = decimal-part + "0" * (places - decimal-part.len())
  
  formatted-integer + "." + decimal-part
}



#let arrange_summary_row(row) = {
  let name = strong(upper(row.at("Name")))
  let description = [#par(justify: true, text(8pt, row.at("Description", default: lorem(35))))]
  let total = if row.at("RateSubtotal") == "" {0.0} else {float(row.at("RateSubtotal"))}
  if row.at("TotalPrice") != "0.0" {
    if row.at("Index") == "1" {
      // ROOT COST
      (
        row.at("Hierarchy"),
        name,
        [],
        strong[#format-decimal(float(row.at("TotalPrice")), places: 2)]        
      )
    } else {
      // SUB CATEGORY
      ( 
        row.at("Hierarchy"),
        table.cell(inset: (left: int(row.at("Index"))*2.5mm))[#upper(row.at("Name"))],
        format-decimal(float(row.at("TotalPrice")), places: 2),
        [],
      )
    }
  }
}



#let arrange_cost_item_row(row) = {
  if row.at("TotalPrice") != "0.0" {
    // CATEGORY
    let name = strong(upper(row.at("Name")))
    let description = [#par(justify: true, text(8pt, row.at("Description", default: lorem(35))))]
    let total_price = format-decimal(float(row.at("TotalPrice", default: "0.0")), places: 2)
  
    (
      [], [], [], [], [], [], [], [], [],
    )
    (
      table.cell(..root-cost-cell-style)[#row.at("Hierarchy")],
      table.cell(..root-cost-cell-style)[#strong(upper(row.at("Name"))) #linebreak() #row.at("Description", default:"")],
      table.cell(..root-cost-cell-style)[],      
      table.cell(..root-cost-cell-style)[],
      table.cell(..root-cost-cell-style)[],
      table.cell(..root-cost-cell-style)[],
      table.cell(..root-cost-cell-style)[],
      table.cell(..root-cost-cell-style)[],
      table.cell(..root-cost-cell-style)[#strong(total_price)],
    ) 
    
  } else {
    // COST ITEM
    let name = strong(upper(row.at("Name")))
    let description = [#par(justify: true, text(8pt, row.at("Description", default: lorem(35))))]
    let unit = table.cell(align: right)[Sum #unit_map.at(row.at("Unit"), default: "")]
    let quant = if row.at("Quantity") == "" {0.0} else {
      format-decimal(float(row.at("Quantity")))}
    let rate = if row.at("RateSubtotal") == "" {0.0} else {
      format-decimal(float(row.at("RateSubtotal")))}
    let total = if row.at("Quantity") == "" {0.0} else {
      format-decimal(float(row.at("Quantity")) * float(row.at("RateSubtotal")), places: 2)}
    
    (
      row.at("Hierarchy"),
      if row.at("Identification") == "" {name + linebreak() + description} else {name + linebreak() + row.at("Identification") +  linebreak() + description},
      [],
      [],
      [],
      [],
      [],
      [],
      [],
    )
    (
      [],
      unit,
      [],
      [],
      [],
      [],
      table.cell(..total-cell-style, align: right + bottom)[#quant],
      table.cell(..total-cell-style, align: right + bottom)[#rate],
      table.cell(..total-cell-style, align: right + bottom)[#total],
    )
    
  }
}



#let csv-table-schedule(path, delimiter: ",") = {
  let data = csv(path, delimiter: delimiter, row-type: dictionary)
  let new_rows = data.map(arrange_cost_item_row)
 
  table(
    columns: (18mm,1fr, 12mm,12mm,12mm,12mm, 20mm, 20mm, 25mm),
    align: (center, left, center, center, center, center, right, right, right),
    stroke: none,
    ..new_rows.flatten()
  )
}



#let csv-table-summary(path, delimiter: ",") = {
  let data = csv(path, delimiter: delimiter, row-type: dictionary)
  let new_rows = data.map(arrange_summary_row)
  let general_total = data.filter(row => row.at("Index") == "1") 
   .map(row => float(row.at("TotalPrice")))
   .sum()
  
  set text(size: 10pt)
  pad(left: 2cm)[SUMMARY:]
  
  set text(size: 8pt)
  table(
    columns: (18mm,107mm, 30mm, 30mm),
    align: (center, left, right, right),
    stroke: (x, y) => (
      left: none,
      right: none,
      top: (dash: "dotted"),
      bottom:  (dash: "dotted")
    ),
    ..new_rows.flatten()
  )
  
  set text(size: 10pt)
  grid(
  columns: (18mm,107mm, 30mm, 30mm),
  align: (center, right, center, right),
  inset: 1mm,
  fill: gray.transparentize(70%),
  [], strong[GENERAL TOTAL:], [],[#strong(format-decimal(general_total, places: 2))]
)
}



#let project(
  schedule_path: "",
  title: "", 
  schedule_name: "", 
  cover_page: bool, 
  root_items_to_new_page: bool,
  summary: bool, 
  body) = {
  // Set the document's basic properties.
  //set document(schedule: schedule_name, title: title)
   
  set page(
    margin: (left: 15mm, right: 10mm, top: 35mm, bottom: 20mm),
    numbering: "1/1",
    number-align: end,
    header:[
      #set text(font: "Liberation Sans", size: 9pt, lang: "en");
      #table(
        columns: (1fr, 2fr),
        rows: 10mm,
        stroke: none,
        inset: 0mm,
        align:(top+left, top+right),
        [#title], [#schedule_name]
      )
    ],
    footer: context [
      #grid(
        columns: (1fr, 1fr),
        align: (left, right),
        [#datetime.today().display("[day]/[month]/[year]")],
        [#counter(page).display("1/1", both: true)]
      )
    ],
    background: 
    place( top + left, dx: 15mm, dy: 25mm,
      table(columns: (18mm,54mm, 12mm,12mm,12mm,12mm, 20mm, 20mm, 25mm),
        rows: (6mm, 248mm),
        align: (center, left, center, center, center, center, center, center, center),
        stroke: (x, y) => (
          left: if x == 0 { 1pt } else { 0.25pt },
          right: 1pt,
          top: 1pt,
          bottom: 1pt
        ),
        [Hierarchy], [Description], [n°],[l],[w],[h/w], [Quantity], [Rate], [Total]
      )
    )
  )

  set text(font: "Liberation Sans", size: 8pt, lang: "en");
      
  csv-table-schedule(schedule_path)
    
  if summary == true {
    pagebreak()
    set text(font: "Liberation Sans", size: 8pt, lang: "en");
    set page(
    background:
      place( top + left, dx: 15mm, dy: 25mm,
        table(columns: (18mm,107mm, 30mm, 30mm),
          rows: (6mm, 248mm),
          align: (center, left, center, center, center, center, center, center, center),
          stroke: (x, y) => (
            left: if x == 0 { 1pt } else { 0.25pt },
            right: 1pt,
            top: 1pt,
            bottom: 1pt
          ),
          text(size: 8pt)[Hierarchy],
          text(size: 8pt)[Description], 
          text(size: 8pt)[Sub Total], 
          text(size: 8pt)[Total]
        )
      )
    )
    csv-table-summary(schedule_path)
  }
}
