/**
 * Scaffolding file used to store all the setups needed to run 
 * tests automatically generated by EvoSuite
 * Mon Mar 18 18:46:49 GMT 2019
 */

package pamvotis.core;

import org.evosuite.runtime.annotation.EvoSuiteClassExclude;
import org.junit.BeforeClass;
import org.junit.Before;
import org.junit.After;
import org.junit.AfterClass;
import org.evosuite.runtime.sandbox.Sandbox;
import org.evosuite.runtime.sandbox.Sandbox.SandboxMode;

@EvoSuiteClassExclude
public class Simulator_ESTest_scaffolding {

  @org.junit.Rule 
  public org.evosuite.runtime.vnet.NonFunctionalRequirementRule nfr = new org.evosuite.runtime.vnet.NonFunctionalRequirementRule();

  private static final java.util.Properties defaultProperties = (java.util.Properties) java.lang.System.getProperties().clone(); 

  private org.evosuite.runtime.thread.ThreadStopper threadStopper =  new org.evosuite.runtime.thread.ThreadStopper (org.evosuite.runtime.thread.KillSwitchHandler.getInstance(), 3000);


  @BeforeClass 
  public static void initEvoSuiteFramework() { 
    org.evosuite.runtime.RuntimeSettings.className = "pamvotis.core.Simulator"; 
    org.evosuite.runtime.GuiSupport.initialize(); 
    org.evosuite.runtime.RuntimeSettings.maxNumberOfThreads = 100; 
    org.evosuite.runtime.RuntimeSettings.maxNumberOfIterationsPerLoop = 10000; 
    org.evosuite.runtime.RuntimeSettings.mockSystemIn = true; 
    org.evosuite.runtime.RuntimeSettings.sandboxMode = org.evosuite.runtime.sandbox.Sandbox.SandboxMode.RECOMMENDED; 
    org.evosuite.runtime.sandbox.Sandbox.initializeSecurityManagerForSUT(); 
    org.evosuite.runtime.classhandling.JDKClassResetter.init();
    setSystemProperties();
    initializeClasses();
    org.evosuite.runtime.Runtime.getInstance().resetRuntime(); 
  } 

  @AfterClass 
  public static void clearEvoSuiteFramework(){ 
    Sandbox.resetDefaultSecurityManager(); 
    java.lang.System.setProperties((java.util.Properties) defaultProperties.clone()); 
  } 

  @Before 
  public void initTestCase(){ 
    threadStopper.storeCurrentThreads();
    threadStopper.startRecordingTime();
    org.evosuite.runtime.jvm.ShutdownHookHandler.getInstance().initHandler(); 
    org.evosuite.runtime.sandbox.Sandbox.goingToExecuteSUTCode(); 
    setSystemProperties(); 
    org.evosuite.runtime.GuiSupport.setHeadless(); 
    org.evosuite.runtime.Runtime.getInstance().resetRuntime(); 
    org.evosuite.runtime.agent.InstrumentingAgent.activate(); 
  } 

  @After 
  public void doneWithTestCase(){ 
    threadStopper.killAndJoinClientThreads();
    org.evosuite.runtime.jvm.ShutdownHookHandler.getInstance().safeExecuteAddedHooks(); 
    org.evosuite.runtime.classhandling.JDKClassResetter.reset(); 
    resetClasses(); 
    org.evosuite.runtime.sandbox.Sandbox.doneWithExecutingSUTCode(); 
    org.evosuite.runtime.agent.InstrumentingAgent.deactivate(); 
    org.evosuite.runtime.GuiSupport.restoreHeadlessMode(); 
  } 

  public static void setSystemProperties() {
 
    java.lang.System.setProperties((java.util.Properties) defaultProperties.clone()); 
    java.lang.System.setProperty("file.encoding", "UTF-8"); 
    java.lang.System.setProperty("java.awt.headless", "true"); 
    java.lang.System.setProperty("java.io.tmpdir", "/tmp"); 
    java.lang.System.setProperty("user.country", "US"); 
    java.lang.System.setProperty("user.dir", "/home/leofernandesmo/workspace-alt/nimrod-hunor/subjects/pamvotis-removenode/nimrod_output/suites/ROR_456/evosuite_2"); 
    java.lang.System.setProperty("user.home", "/home/leofernandesmo"); 
    java.lang.System.setProperty("user.language", "en"); 
    java.lang.System.setProperty("user.name", "leofernandesmo"); 
    java.lang.System.setProperty("user.timezone", "America/Maceio"); 
  }

  private static void initializeClasses() {
    org.evosuite.runtime.classhandling.ClassStateSupport.initializeClasses(Simulator_ESTest_scaffolding.class.getClassLoader() ,
      "pamvotis.core.Packet",
      "pamvotis.sources.RandomGenerator",
      "pamvotis.exceptions.ConfigurationException",
      "pamvotis.core.Params",
      "pamvotis.sources.GenericSource",
      "pamvotis.core.SpecParams",
      "pamvotis.sources.HTTPSource",
      "pamvotis.exceptions.UnknownDistributionException",
      "pamvotis.core.PacketBuffer",
      "pamvotis.sources.VideoSource",
      "pamvotis.exceptions.ElementExistsException",
      "pamvotis.core.Simulator",
      "pamvotis.core.SourceManager",
      "pamvotis.exceptions.ElementDoesNotExistException",
      "pamvotis.sources.Source",
      "pamvotis.core.MobileNode",
      "pamvotis.sources.FTPSource",
      "pamvotis.core.VirtualPacket"
    );
  } 

  private static void resetClasses() {
    org.evosuite.runtime.classhandling.ClassResetter.getInstance().setClassLoader(Simulator_ESTest_scaffolding.class.getClassLoader()); 

    org.evosuite.runtime.classhandling.ClassStateSupport.resetClasses(
      "pamvotis.core.Simulator",
      "pamvotis.core.SpecParams",
      "pamvotis.core.MobileNode",
      "pamvotis.exceptions.ElementDoesNotExistException",
      "pamvotis.sources.Source",
      "pamvotis.core.Params",
      "pamvotis.core.SourceManager",
      "pamvotis.core.PacketBuffer",
      "pamvotis.sources.GenericSource",
      "pamvotis.exceptions.UnknownDistributionException",
      "pamvotis.sources.VideoSource",
      "pamvotis.sources.RandomGenerator",
      "pamvotis.core.VirtualPacket",
      "pamvotis.sources.HTTPSource"
    );
  }
}
