import unittest

from xml.dom import minidom
from xml.etree import cElementTree as etree
from commonpylib.util import IntAttribute, AttributesList, getExp, getList 
from commonpylib.log import title, UniBorder

from mltester.actions.step import Step

###############################################################################

@Step.REGISTER()
class DemoStep1(Step):
    NAME = "Demo Step 1"
    ATTRIBUTES = [IntAttribute("a", "ATTR1", ""), 
                  IntAttribute("b", "ATTR2", ""),
                  IntAttribute("c", "ATTR3", "")]

###############################################################################

@Step.REGISTER()
class DemoStep2(Step):
    NAME = "Demo Step 2"
    ATTRIBUTES = [IntAttribute("a", "TEST1", ""), 
                  IntAttribute("b", "TEST2", ""),
                  IntAttribute("c", "TEST3", "")]

expected_xml = \
'''<?xml version="1.0" ?>
<root>
\t<Step Class="Demo Step 1">
\t\t<Name Value="A test step #1"/>
\t\t<Enabled Value="False"/>
\t\t<Repeat Value="20"/>
\t\t<Attributes>
\t\t\t<Attribute Name="a" Value="1"/>
\t\t\t<Attribute Name="b" Value="2"/>
\t\t\t<Attribute Name="c" Value="3"/>
\t\t</Attributes>
\t</Step>
\t<Step Class="Demo Step 1">
\t\t<Name Value="Demo Step 1"/>
\t\t<Enabled Value="True"/>
\t\t<Repeat Value="1"/>
\t\t<Attributes>
\t\t\t<Attribute Name="a" Value="4"/>
\t\t\t<Attribute Name="b" Value="5"/>
\t\t\t<Attribute Name="c" Value="6"/>
\t\t</Attributes>
\t</Step>
\t<Step Class="Demo Step 2">
\t\t<Name Value="Demo Step 2"/>
\t\t<Enabled Value="True"/>
\t\t<Repeat Value="1"/>
\t\t<Attributes>
\t\t\t<Attribute Name="a" Value="1"/>
\t\t\t<Attribute Name="b" Value="2"/>
\t\t\t<Attribute Name="c" Value="3"/>
\t\t</Attributes>
\t</Step>
\t<Step Class="Demo Step 2">
\t\t<Name Value="Demo Step 2"/>
\t\t<Enabled Value="True"/>
\t\t<Repeat Value="1"/>
\t\t<Attributes>
\t\t\t<Attribute Name="a" Value="4"/>
\t\t\t<Attribute Name="b" Value="5"/>
\t\t\t<Attribute Name="c" Value="6"/>
\t\t</Attributes>
\t</Step>
</root>
'''

###############################################################################
        
class StepTest(unittest.TestCase):

    def test_step(self):
        ''' Test Attributes '''
    
        xml = etree.Element("root")
    
        step1 = DemoStep1(values=[1, 2, 3])
        step2 = DemoStep1(values=[4, 5, 6])
        step3 = DemoStep2(values=[1, 2, 3])
        step4 = DemoStep2(values=[4, 5, 6])
        
        step1.setEnabled(False)
        step1.setRepeat(20)
        step1.setName("A test step #1")

        self.assertEqual(step1.name(), "A test step #1")
        self.assertEqual(step2.name(), DemoStep1.NAME)
        self.assertEqual(step3.name(), DemoStep2.NAME)
        self.assertEqual(step4.name(), DemoStep2.NAME)
                
        self.assertEqual(step1.a, 1)
        self.assertEqual(step1.b, 2)
        self.assertEqual(step1.c, 3)
        self.assertEqual(step2.a, 4)
        self.assertEqual(step2.b, 5)
        self.assertEqual(step2.c, 6)
        self.assertEqual(step3.a, 1)
        self.assertEqual(step3.b, 2)
        self.assertEqual(step3.c, 3)
        self.assertEqual(step4.a, 4)
        self.assertEqual(step4.b, 5)
        self.assertEqual(step4.c, 6)

        #################
        # Write to xml: #
        #################
        step1.writeToXml(xml)
        step2.writeToXml(xml)
        step3.writeToXml(xml)
        step4.writeToXml(xml)            
    
        content = minidom.parseString(etree.tostring(xml)).toprettyxml()
        self.assertEqual(content, expected_xml)
        
        ##################
        # Load from xml: #
        ##################
        root_node = etree.fromstring(content)
        steps = []
        for step_node in root_node.getchildren():
            steps.append(Step.loadFromXml(step_node))
            
        step1 = steps[0]
        step2 = steps[1]
        step3 = steps[2]
        step4 = steps[3]
            
        self.assertEqual(step1.name(), "A test step #1")
        self.assertEqual(step2.name(), DemoStep1.NAME)
        self.assertEqual(step3.name(), DemoStep2.NAME)
        self.assertEqual(step4.name(), DemoStep2.NAME)
                
        self.assertEqual(step1.a, 1)
        self.assertEqual(step1.b, 2)
        self.assertEqual(step1.c, 3)
        self.assertEqual(step2.a, 4)
        self.assertEqual(step2.b, 5)
        self.assertEqual(step2.c, 6)
        self.assertEqual(step3.a, 1)
        self.assertEqual(step3.b, 2)
        self.assertEqual(step3.c, 3)
        self.assertEqual(step4.a, 4)
        self.assertEqual(step4.b, 5)
        self.assertEqual(step4.c, 6)            

# --------------------------------------------------------------------------- #
        
if __name__ == '__main__':
    unittest.main()

