import org.apache.lucene.codecs.*;import org.apache.lucene.index.*;import org.apache.lucene.store.*;import org.apache.lucene.search.DocIdSetIterator;
import java.nio.file.*;import java.io.*;import java.util.*;
/** Extract all stored pages of given Shamela book ids from ONE Lucene segment of store/page.
 *  usage: ExtractBooks <dir> <seg> <fnmGen|-> <outDir> <bookId>...   → <outDir>/<bookId>.jsonl  (fields: id, body, foot, ...) */
public class ExtractBooks{
  static String esc(String s){StringBuilder b=new StringBuilder();for(char c:s.toCharArray()){switch(c){case '"':b.append("\\\"");break;case '\\':b.append("\\\\");break;case '\n':b.append("\\n");break;case '\r':b.append("\\r");break;case '\t':b.append("\\t");break;default:if(c<0x20)b.append(String.format("\\u%04x",(int)c));else b.append(c);}}return b.toString();}
  public static void main(String[] a)throws Exception{
    Path p=Paths.get(a[0]);String seg=a[1];String gen=a[2].equals("-")?"":a[2];Path out=Paths.get(a[3]);Files.createDirectories(out);
    Map<Long,List<Integer>> docs=new TreeMap<>();for(int i=4;i<a.length;i++)docs.put(Long.parseLong(a[i]),new ArrayList<>());
    byte[] si=Files.readAllBytes(p.resolve(seg+".si"));int off=4;int n=si[off];off+=1+n+4;byte[] id=Arrays.copyOfRange(si,off,off+16);
    Directory dir=new NIOFSDirectory(p);Codec c=Codec.forName("Lucene104");SegmentInfo info=c.segmentInfoFormat().read(dir,seg,id,IOContext.DEFAULT);
    Directory cfs=info.getUseCompoundFile()?c.compoundFormat().getCompoundReader(dir,info):dir;
    FieldInfos fis=c.fieldInfosFormat().read(gen.isEmpty()?cfs:dir,info,gen,IOContext.DEFAULT);
    DocValuesProducer dvp=c.docValuesFormat().fieldsProducer(new SegmentReadState(cfs,info,fis,IOContext.DEFAULT,""));
    NumericDocValues dv=dvp.getNumeric(fis.fieldInfo("book"));
    for(int d=dv.nextDoc();d!=DocIdSetIterator.NO_MORE_DOCS;d=dv.nextDoc()){List<Integer> l=docs.get(dv.longValue());if(l!=null)l.add(d);}
    StoredFieldsReader r=c.storedFieldsFormat().fieldsReader(cfs,info,fis,IOContext.DEFAULT);
    for(var e:docs.entrySet()){ if(e.getValue().isEmpty())continue;
      try(Writer w=new BufferedWriter(new OutputStreamWriter(new FileOutputStream(out.resolve(e.getKey()+".jsonl").toFile()),"UTF-8"))){
        for(int d:e.getValue()){ final Map<String,String> m=new LinkedHashMap<>();
          r.document(d,new StoredFieldVisitor(){public Status needsField(FieldInfo fi){return Status.YES;}
            public void stringField(FieldInfo fi,String v){m.merge(fi.name,v,(x,y)->x+"\u0001"+y);}
            public void intField(FieldInfo fi,int v){m.put(fi.name,""+v);} public void longField(FieldInfo fi,long v){m.put(fi.name,""+v);}});
          StringBuilder b=new StringBuilder("{\"_doc\":\""+d+"\"");for(var f:m.entrySet())b.append(",\"").append(esc(f.getKey())).append("\":\"").append(esc(f.getValue())).append('"');
          w.write(b.append("}\n").toString());}}
      System.err.println("book "+e.getKey()+": "+e.getValue().size()+" pages");}
  }}
