// Jake's-resume layout in Typst. All black, one page, real links.
// Rules live in career/wiki/resume-rules.md; do not restyle per job.

#let resume(name: "", contact: (), body) = {
  set document(title: name + " — Resume", author: name)
  set page(paper: "us-letter", margin: (x: 0.42in, top: 0.36in, bottom: 0.3in))
  set text(font: "New Computer Modern", size: 9.6pt, fill: black, hyphenate: false)
  set par(justify: false, leading: 0.46em, spacing: 0.46em)
  show link: it => it

  align(center)[
    #text(size: 22pt, weight: "bold", tracking: 0.02em)[#smallcaps(name)]
    #v(-0.55em)
    #text(size: 9.2pt)[#contact.join([#h(0.45em)|#h(0.45em)])]
  ]
  v(-0.25em)
  body
}

#let section(title) = block(above: 0.7em, below: 0.46em, sticky: true)[
  #text(size: 11pt, weight: "bold")[#smallcaps(title)]
  #v(-0.52em)
  #line(length: 100%, stroke: 0.5pt + black)
]

// Bold headline left / dates right, italic role left / location right, stack line, bullets.
#let entry(org, dates, role: none, place: none, stack: none, bullets: ()) = {
  block(spacing: 0.56em, breakable: false)[
    #grid(columns: (1fr, auto), row-gutter: 0.36em,
      [*#org*], [#dates],
      ..if role != none or place != none { ([_#role _], [_#place _]) } else { () },
    )
    #if stack != none [
      #v(-0.12em)
      #text(size: 8.8pt)[*Stack:* #stack]
    ]
    #if bullets.len() > 0 {
      v(-0.14em)
      pad(left: 0.9em, list(marker: [•], spacing: 0.34em, indent: 0em, body-indent: 0.45em, ..bullets))
    }
  ]
}

// One-line project: name (linked) — description, with optional stack in parentheses.
#let item(name, desc) = block(spacing: 0.34em)[
  #pad(left: 0.9em)[#h(-0.9em)• #h(0.2em)*#name* — #desc]
]

#let skills(rows) = block(spacing: 0.3em)[
  #for (k, v) in rows [*#k:* #v \ ]
]

#let u(url, label) = link(url)[#underline(offset: 1.6pt, stroke: 0.4pt)[#label]]
