from app.services.xml_parser import parse_cfdi_xml


def test_parse_cfdi_xml_extrae_datos_basicos():
    xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4"
                  xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital"
                  Total="116.00"
                  SubTotal="100.00"
                  Descuento="5.00"
                  Moneda="MXN"
                  MetodoPago="PUE"
                  Folio="A-100"
                  Fecha="2024-05-10T10:00:00">
  <cfdi:Emisor Rfc="AAA010101AAA" Nombre="Proveedor Demo" />
  <cfdi:Receptor Rfc="BBB010101BBB" />
  <cfdi:Impuestos>
    <cfdi:Traslados>
      <cfdi:Traslado Impuesto="002" Importe="16.00" />
      <cfdi:Traslado Impuesto="003" Importe="8.00" />
    </cfdi:Traslados>
    <cfdi:Retenciones>
      <cfdi:Retencion Impuesto="001" Importe="10.00" />
      <cfdi:Retencion Impuesto="002" Importe="4.00" />
    </cfdi:Retenciones>
  </cfdi:Impuestos>
  <cfdi:Complemento>
    <tfd:TimbreFiscalDigital UUID="123e4567-e89b-12d3-a456-426614174000" />
  </cfdi:Complemento>
</cfdi:Comprobante>
"""

    data = parse_cfdi_xml(xml)

    assert data.uuid == "123E4567-E89B-12D3-A456-426614174000"
    assert data.razon_social == "Proveedor Demo"
    assert data.rfc_emisor == "AAA010101AAA"
    assert data.rfc_receptor == "BBB010101BBB"
    assert data.subtotal == 100
    assert data.descuento == 5
    assert data.total == 116
    assert data.iva == 16
    assert data.iva_trasladado == 16
    assert data.ieps_trasladado == 8
    assert data.iva_retenido == 4
    assert data.isr_retenido == 10
    assert data.total_impuestos_trasladados == 24
    assert data.total_impuestos_retenidos == 14
    assert data.moneda == "MXN"
    assert data.metodo_pago == "PUE"
