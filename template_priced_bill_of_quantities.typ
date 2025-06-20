// PRICED BILL OF QUANTITIES TEMPLATE
// author: carlo pavan
// year: 2025

// custom cell styles
#let total-cell-style = (stroke: (top: 0.25pt + gray))
#let root-cost-cell-style = (stroke: (bottom: (dash: "dotted")), fill: gray.transparentize(90%))


// custom numbers styles
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



#let euro(num) = {
  str(calc.round(float(num), digits: 2)) + " €"
}



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



#let read-csv(path, delimiter: ",") = {
  let lines = read(path).split("\n").filter(l => l != "")
  let header = lines.at(0).split(delimiter).map(f => f.trim())
  let rows = lines.slice(1).map(line => {
    let values = line.split(delimiter).map(f => f.trim())
    let row-dict = (:)
    for (i, col) in header.enumerate() {
      row-dict.insert(col, values.at(i, default: ""))
    }
    row-dict
  })
  (header: header, rows: rows)
}



#let csv-table-schedule(path, delimiter: ",") = {
  let data = read-csv(path, delimiter: delimiter)
  let new_rows = ()
  
  for row in data.rows {
    let new-cell = ()

    if row.at("TotalPrice") != "0.0"{
      // NEW ROOT COST / CHAPTER
      new-cell.push([#colbreak()]) // new root cost to new page: DOES NOT WORK
      new-cell.push([])
      new-cell.push([])
      new-cell.push([])
      new-cell.push([])
      new-cell.push([])
      new-cell.push([])      
      new-cell.push([])
      new-cell.push([])
      
      new-cell.push(table.cell(..root-cost-cell-style)[#row.at("Hierarchy")])
      new-cell.push(table.cell(..root-cost-cell-style)[#strong(upper(row.at("Name"))) #linebreak() #row.at("Description", default:lorem(5))])
      new-cell.push(table.cell(..root-cost-cell-style)[])
      new-cell.push(table.cell(..root-cost-cell-style)[])
      new-cell.push(table.cell(..root-cost-cell-style)[])
      new-cell.push(table.cell(..root-cost-cell-style)[])
      new-cell.push(table.cell(..root-cost-cell-style)[])
      new-cell.push(table.cell(..root-cost-cell-style)[])
      new-cell.push(table.cell(..root-cost-cell-style)[#strong(format-decimal(float(row.at("TotalPrice")), places: 2))])
    } else {
        // NEW COST ITEM
        if row.at("Identification") != "" {
        new-cell.push(row.at("Hierarchy"))
        new-cell.push(strong(row.at("Name")) + "\n" + text(font: "Liberation Mono", row.at("Identification")))
        new-cell.push([])
        new-cell.push([])
        new-cell.push([])
        new-cell.push([])
        new-cell.push([])
        new-cell.push([])
        new-cell.push([])
      } else {
        new-cell.push(row.at("Hierarchy"))
        new-cell.push(strong(row.at("Name")))
        new-cell.push([])
        new-cell.push([])
        new-cell.push([])
        new-cell.push([])
        new-cell.push([])
        new-cell.push([])
        new-cell.push([])
      }
    
      new-cell.push([])
      new-cell.push(par(justify: true, text(row.at("Description", default:lorem(25)))))
      new-cell.push([])
      new-cell.push([])
      new-cell.push([])
      new-cell.push([])
      new-cell.push([])
      new-cell.push([])
      new-cell.push([])
  
      new-cell.push([])
      new-cell.push(table.cell(align: right)[Sum #unit_map.at(row.at("Unit"), default: "")])
      new-cell.push([])
      new-cell.push([])
      new-cell.push([])
      new-cell.push([])
      // Cost item total. Perhaps better format it in python right in the csv, so it's not necessary to perform those operations in typst
      if row.at("Quantity") == "" {
        new-cell.push(table.cell(
          stroke: (top: 0.25pt + gray))[0.00])
        new-cell.push(table.cell(..total-cell-style)[#row.at("RateSubtotal")])
        new-cell.push((table.cell(..total-cell-style)[0.00]))
      } 
      else {
        new-cell.push(table.cell(..total-cell-style)[#format-decimal(float(row.at("Quantity")), places: 2)])
        new-cell.push(table.cell(..total-cell-style)[#row.at("RateSubtotal")])
        new-cell.push(table.cell(..total-cell-style)[#format-decimal(float(row.at("Quantity")) * float(row.at("RateSubtotal")), places: 2)])
      }
    }
    
    
    new_rows.push(new-cell)
  }
  table(
    columns: (18mm,1fr, 12mm,12mm,12mm,12mm, 20mm, 20mm, 25mm),
    align: (center, left, center, center, center, center, right, right, right),
    stroke: none,
    ..new_rows.flatten()
  )
}



#let csv-table-summary(path, delimiter: ",") = {
  let data = read-csv(path, delimiter: delimiter)
  let new_rows = ()
  
  for row in data.rows {
    let new-cell = ()
    if row.at("TotalPrice") != "0.0" {
      new-cell.push(row.at("Hierarchy"))
      if row.at("Index") == "1" {
        // ROOT COST
        new-cell.push(strong[#row.at("Name")])
    new-cell.push(row.at("General Cost"))
    new-cell.push(strong[#format-decimal(float(row.at("TotalPrice")), places: 2)])
      } else {
        // SUB CATEGORY
        new-cell.push(table.cell(inset: (left: int(row.at("Index"))*2.5mm))[#row.at("Name")])
        new-cell.push(format-decimal(float(row.at("TotalPrice")), places: 2))
        new-cell.push([])
      }

    }

  new_rows.push(new-cell)
  }
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
}



#let project(
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
      
  csv-table-schedule("schedule.csv")
    
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
    set text(font: "Liberation Sans", size: 8pt, lang: "en");
    
    csv-table-summary("schedule.csv")
    
  }
}
