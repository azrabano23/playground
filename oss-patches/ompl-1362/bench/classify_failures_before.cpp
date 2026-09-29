// Classifies why the *old* high-altitude root finding in OwenStateSpace::getPath fails (ompl#1362).
// Re-runs the exact old bracket_and_solve_root call and checks the final bracket:
//  - "tolerance": f is continuous across the bracket and one end is ~0, but the midpoint misses the 1e-5 check
//  - "jump": f jumps across the bracket (discontinuity of the shortest Dubins length)
// Usage: classify_failures_before <boundsHalfWidth>   (turn radius 1, max pitch pi/6, seed 1)
#include <ompl/base/spaces/OwenStateSpace.h>
#include <ompl/util/RandomNumbers.h>
#include <boost/math/tools/toms748_solve.hpp>
#include <cstdio>
#include <cmath>
#include <map>
namespace ob=ompl::base;
int main(int argc,char**argv){
  double half=std::stod(argv[1]);
  ompl::RNG::setSeed(1);
  auto sp=std::make_shared<ob::OwenStateSpace>(1., M_PI/6); ob::RealVectorBounds b(3); b.setLow(-half); b.setHigh(half); sp->setBounds(b); sp->setup();
  auto smp=sp->allocDefaultStateSampler(); auto *a=sp->allocState(),*c=sp->allocState();
  double tanP=std::tan(M_PI/6); std::map<std::string,int> cnt; int shown=0;
  for(int i=0;i<100000;i++){ smp->sampleUniform(a); smp->sampleUniform(c);
    auto *s1=a->as<ob::OwenStateSpace::StateType>(),*s2=c->as<ob::OwenStateSpace::StateType>();
    double dz=(*s2)[2]-(*s1)[2]; double len=ob::DubinsStateSpace::getPath(a,c,1.).length();
    if(!(std::abs(dz)>(len+2*M_PI)*tanP)) continue;
    unsigned k=std::floor((std::abs(dz)/tanP-len)/(2*M_PI));
    auto f=[&](double r){return (ob::DubinsStateSpace::getPath(a,c,r).length()+2*M_PI*k)*r*tanP-std::abs(dz);};
    std::uintmax_t it=32; std::pair<double,double> res;
    try{ res=boost::math::tools::bracket_and_solve_root(f,1.,2.,true,boost::math::tools::eps_tolerance<double>(20),it);}catch(...){cnt["throw"]++;continue;}
    double r=.5*(res.first+res.second), g=f(r);
    if(std::abs(g)<=1e-5){cnt["ok"]++;continue;}
    double fa=f(res.first), fb=f(res.second);
    std::string why;
    if((fa<=0)==(fb<=0)) why="no sign change in final bracket";
    else if(std::abs(fa)<1e-3*1+ (res.second-res.first)*100 && std::abs(fb)<1e-3+(res.second-res.first)*100) why= it>=32? "iter limit, continuous":"tolerance (continuous, bracket too wide for 1e-5 check)";
    else why="jump across bracket (discontinuity)";
    cnt[why]++;
    if(shown<4 && why[0]=='j'){shown++; std::printf("jump: [%g,%g] fa=%g fb=%g it=%lu\n",res.first,res.second,fa,fb,(unsigned long)it);}
    if(shown<8 && why[0]!='j'){shown++; std::printf("%s: [%.9g,%.9g] fa=%g fb=%g g=%g it=%lu\n",why.c_str(),res.first,res.second,fa,fb,g,(unsigned long)it);}
  }
  for(auto&p:cnt) std::printf("%-55s %d\n",p.first.c_str(),p.second);
}
