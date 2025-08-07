import { Document, Paragraph, Table, TableRow, TableCell, TextRun, HeadingLevel, AlignmentType, BorderStyle, WidthType, convertInchesToTwip } from 'docx';
import { saveAs } from 'file-saver';
import { Packer } from 'docx';

interface Section {
  title: string;
  content: string;
  order: number;
}

export class WordExporter {
  static async exportToWord(sections: Section[], title: string) {
    const doc = new Document({
      styles: {
        default: {
          heading1: {
            run: {
              font: "Aptos Display",
              size: 32,
              bold: true,
              color: "2B579A",
            },
            paragraph: {
              spacing: { before: 240, after: 120 },
            },
          },
          heading2: {
            run: {
              font: "Aptos Display",
              size: 28,
              bold: true,
              color: "2B579A",
            },
            paragraph: {
              spacing: { before: 240, after: 120 },
            },
          },
          heading3: {
            run: {
              font: "Aptos Body",
              size: 24,
              bold: true,
            },
            paragraph: {
              spacing: { before: 120, after: 120 },
            },
          },
        },
        paragraphStyles: [
          {
            id: "Normal",
            name: "Normal",
            basedOn: "Normal",
            next: "Normal",
            run: {
              font: "Aptos Body",
              size: 22, // 11pt = 22 half-points
            },
            paragraph: {
              spacing: { line: 360, after: 120 }, // 1.5 line spacing
            },
          },
        ],
      },
      sections: [{
        properties: {},
        children: [
          // Title page
          new Paragraph({
            text: title,
            heading: HeadingLevel.TITLE,
            alignment: AlignmentType.CENTER,
            spacing: { before: 240, after: 480 },
          }),
          new Paragraph({
            text: `Generated on ${new Date().toLocaleDateString()}`,
            alignment: AlignmentType.CENTER,
            spacing: { after: 240 },
          }),
          // Page break
          new Paragraph({
            text: "",
            pageBreakBefore: true,
          }),
          // Process each section
          ...this.processAllSections(sections),
        ],
      }],
    });

    const blob = await Packer.toBlob(doc);
    saveAs(blob, `PRD_${new Date().toISOString().split('T')[0]}.docx`);
  }

  private static processAllSections(sections: Section[]): any[] {
    const elements: any[] = [];
    
    sections.sort((a, b) => a.order - b.order).forEach(section => {
      // Add section title
      elements.push(
        new Paragraph({
          text: section.title,
          heading: HeadingLevel.HEADING_2,
          spacing: { before: 240, after: 120 },
        })
      );
      
      // Process section content
      elements.push(...this.processContent(section.content));
    });
    
    return elements;
  }

  private static processContent(content: string): any[] {
    const elements: any[] = [];
    const lines = content.split('\n');
    
    let inTable = false;
    let tableData: string[][] = [];
    let inList = false;
    let listItems: string[] = [];
    
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim();
      
      // Skip separator lines
      if (line.match(/^[-—]+$/)) continue;
      
      // Handle tables
      if (line.includes('|') && line.split('|').length > 2) {
        if (!inTable) {
          inTable = true;
          tableData = [];
        }
        const cells = line.split('|').map(c => c.trim()).filter(c => c);
        tableData.push(cells);
      } else if (inTable) {
        // End of table, create the table
        if (tableData.length > 0) {
          // Filter out separator rows (containing only dashes)
          const cleanedData = tableData.filter(row => 
            !row.every(cell => cell.match(/^[-—]+$/))
          );
          if (cleanedData.length > 0) {
            elements.push(this.createTable(cleanedData));
          }
        }
        inTable = false;
        tableData = [];
        
        // Process current line if it's not empty
        if (line) {
          i--; // Reprocess this line
          continue;
        }
      }
      
      // Handle bullet points (various formats)
      else if (line.match(/^[•\-\*]\s+/)) {
        if (!inList) {
          inList = true;
          listItems = [];
        }
        listItems.push(line.replace(/^[•\-\*]\s+/, '').trim());
      } else if (inList && line && !line.match(/^[•\-\*]\s+/)) {
        // End of list
        if (listItems.length > 0) {
          elements.push(...this.createBulletList(listItems));
        }
        inList = false;
        listItems = [];
        i--; // Reprocess this line
        continue;
      }
      
      // Handle headings
      else if (line.startsWith('###')) {
        elements.push(
          new Paragraph({
            text: line.replace(/^###\s*/, ''),
            heading: HeadingLevel.HEADING_3,
            spacing: { before: 120, after: 120 },
          })
        );
      }
      // Handle bold text patterns
      else if (line.match(/^(Goals|Non-goals|Non-Goals|Objective|KR\d+):/i)) {
        const [label, ...rest] = line.split(':');
        elements.push(
          new Paragraph({
            children: [
              new TextRun({
                text: label + ':',
                bold: true,
                font: "Aptos Body",
                size: 22,
              }),
              new TextRun({
                text: rest.join(':').trim(),
                font: "Aptos Body",
                size: 22,
              }),
            ],
            spacing: { before: 120, after: 60 },
          })
        );
      }
      // Regular paragraph
      else if (line && !inTable && !inList) {
        elements.push(
          new Paragraph({
            text: line,
            spacing: { after: 120 },
            style: "Normal",
          })
        );
      }
    }
    
    // Handle any remaining list
    if (inList && listItems.length > 0) {
      elements.push(...this.createBulletList(listItems));
    }
    
    // Handle any remaining table
    if (inTable && tableData.length > 0) {
      const cleanedData = tableData.filter(row => 
        !row.every(cell => cell.match(/^[-—]+$/))
      );
      if (cleanedData.length > 0) {
        elements.push(this.createTable(cleanedData));
      }
    }
    
    return elements;
  }

  // Add this new helper method right after processContent
  private static cleanHtmlContent(text: string): string {
    // More comprehensive HTML cleaning
    let cleaned = text
      // Handle line breaks - multiple variations
      .replace(/<br\s*\/?>/gi, '\n')
      .replace(/<br>/gi, '\n')
      .replace(/\\n/g, '\n')
      // Handle lists completely
      .replace(/<\/?ul>/gi, '')
      .replace(/<\/?ol>/gi, '')
      .replace(/<li>/gi, '• ')
      .replace(/<\/li>/gi, '')
      // Remove all HTML tags but keep text
      .replace(/<\/?strong>/gi, '')
      .replace(/<\/?b>/gi, '')
      .replace(/<\/?em>/gi, '')
      .replace(/<\/?i>/gi, '')
      // Handle markdown bold
      .replace(/\*\*(.*?)\*\*/g, '$1')
      // Fix multiple bullets
      .replace(/•\s*•/g, '•')
      // Clean up whitespace
      .replace(/\n{3,}/g, '\n\n')
      .replace(/^\s+|\s+$/gm, '') // Trim each line
      .trim();
    
    return cleaned;
  }

  // Update the createTable method to handle complex cell content
  private static createTable(data: string[][]): Table {
    // Process and clean each cell
    const processedData = data.map((row, rowIndex) => 
      row.map(cell => {
        // Clean HTML content from cells
        const cleanedCell = this.cleanHtmlContent(cell);
        
        // Split by newlines to handle multi-line content
        const lines = cleanedCell.split('\n').filter(line => line.trim());
        
        // Detect if this cell contains bullet points
        const hasBullets = lines.some(line => line.trim().startsWith('•'));
        
        return {
          text: cleanedCell,
          lines: lines,
          hasBullets: hasBullets,
          isHeader: rowIndex === 0
        };
      })
    );
    
    const table = new Table({
      width: {
        size: 100,
        type: WidthType.PERCENTAGE,
      },
      borders: {
        top: { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" },
        bottom: { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" },
        left: { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" },
        right: { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" },
        insideHorizontal: { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" },
        insideVertical: { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" },
      },
      rows: processedData.map((row, rowIndex) => 
        new TableRow({
          children: row.map(cellData => {
            const cellChildren: Paragraph[] = [];
            
            if (cellData.hasBullets) {
              // Process each line
              cellData.lines.forEach(line => {
                if (line.trim().startsWith('•')) {
                  // It's a bullet point
                  cellChildren.push(
                    new Paragraph({
                      children: [
                        new TextRun({
                          text: line.replace(/^\s*•\s*/, ''),
                          font: "Aptos Body",
                          size: 20,
                        }),
                      ],
                      bullet: {
                        level: 0
                      },
                      spacing: { after: 20 },
                    })
                  );
                } else if (line.trim()) {
                  // Regular text line
                  cellChildren.push(
                    new Paragraph({
                      children: [
                        new TextRun({
                          text: line,
                          bold: cellData.isHeader,
                          font: "Aptos Body",
                          size: 20,
                        }),
                      ],
                      spacing: { after: 40 },
                    })
                  );
                }
              });
            } else {
              // Simple cell - just add the text
              cellChildren.push(
                new Paragraph({
                  children: [
                    new TextRun({
                      text: cellData.text || ' ', // Ensure non-empty
                      bold: cellData.isHeader,
                      font: "Aptos Body",
                      size: 20,
                    }),
                  ],
                })
              );
            }
            
            return new TableCell({
              children: cellChildren,
              shading: cellData.isHeader ? { fill: "F0F0F0" } : undefined,
            });
          })
        })
      ),
    });
    
    return table;
  }

  private static createBulletList(items: string[]): Paragraph[] {
    return items.map(item => 
      new Paragraph({
        children: [
          new TextRun({
            text: item,
            font: "Aptos Body",
            size: 22,
          }),
        ],
        bullet: {
          level: 0,
        },
        spacing: { after: 60 },
        indent: {
          left: convertInchesToTwip(0.5),
          hanging: convertInchesToTwip(0.25),
        },
      })
    );
  }
}